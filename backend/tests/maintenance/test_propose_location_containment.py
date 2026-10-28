import csv

from maintenance.propose_location_containment import (
    climb,
    containers,
    count_values,
    propose_location_containment,
)
from models import Category, CategoryType, Episode, EpisodeCategory

LINKS = {
    "Raval": [("P131", "Barcelona")],
    "Barcelona": [("P131", "Catalunya"), ("P361", "Àrea metropolitana")],
    "Catalunya": [("P17", "Espanya"), ("P361", "Corona d'Aragó")],
    "Espanya": [("P30", "Europa")],
    "França": [("P30", "Europa")],
    "París": [("P17", "França")],
    "Corona d'Aragó": [("P17", "Itàlia")],
    # A range in two countries, whose divisions are on both sides.
    "Pirineus": [
        ("P17", "Espanya"),
        ("P17", "França"),
        ("P131", "Catalunya"),
    ],
    "Alt Urgell": [("P131", "Catalunya"), ("P706", "Pirineus")],
    # A town's comarca and its province are both true.
    "Capellades": [("P131", "Anoia"), ("P131", "Província de Barcelona")],
    # Two items for the same place.
    "Xina": [("P361", "República Popular de la Xina")],
    "República Popular de la Xina": [("P361", "Xina")],
}


def inside(item: str) -> dict[str, list[str]]:
    return containers(LINKS, count_values(LINKS), item)


class TestContainers:
    def test_climbs_divisions_then_a_country_then_a_continent(self):
        assert inside("Raval") == {
            "Barcelona": ["P131"],
            "Àrea metropolitana": ["P131", "P361"],
            "Catalunya": ["P131", "P131"],
            "Corona d'Aragó": ["P131", "P131", "P361"],
            "Espanya": ["P131", "P131", "P17"],
            "Europa": ["P131", "P131", "P17", "P30"],
        }

    def test_part_of_never_leads_to_a_country(self):
        # The Crown of Aragon's countries include Italy; Catalonia's don't.
        assert "Itàlia" not in inside("Catalunya")

    def test_a_physical_feature_ends_the_climb(self):
        found = inside("Alt Urgell")

        assert "Pirineus" in found
        assert "França" not in found

    def test_ignores_what_spans_several_countries(self):
        assert inside("Pirineus") == {}

    def test_follows_every_division(self):
        assert set(inside("Capellades")) == {"Anoia", "Província de Barcelona"}


class FakeWikipedia:
    """Answers title queries with each article's Wikidata item."""

    def __init__(self, items: dict[str, str], disambiguation=()):
        self.items = items
        self.disambiguation = set(disambiguation)

    def _query(self, titles, **params):
        pages = []
        for title in titles.split("|"):
            if title not in self.items:
                pages.append({"title": title, "missing": True})
                continue
            props = {"wikibase_item": self.items[title]}
            if title in self.disambiguation:
                props["disambiguation"] = ""
            pages.append({"title": title, "pageprops": props})
        return {"pages": pages}


class FakeWikidata:
    def __init__(self, links):
        self.links_by_item = links
        self.asked = []

    def links(self, items, properties):
        items = list(items)
        self.asked.append(items)
        return {item: self.links_by_item.get(item, []) for item in items}


class TestClimb:
    def test_asks_for_each_level_once(self):
        wikidata = FakeWikidata(LINKS)

        found = climb(wikidata, {"Raval", "París"})

        assert wikidata.asked[0] == ["París", "Raval"]
        assert wikidata.asked[1] == ["Barcelona", "França"]
        assert "Europa" in found

    def test_stops_one_level_past_part_of(self):
        links = {
            "Barcelona": [("P361", "Àrea metropolitana")],
            "Àrea metropolitana": [("P361", "Regió")],
            "Regió": [("P361", "Més amunt")],
        }
        wikidata = FakeWikidata(links)

        climb(wikidata, {"Barcelona"})

        assert wikidata.asked == [["Barcelona"], ["Àrea metropolitana"]]


class TestProposeLocationContainment:
    TAGS = {
        "El Tractat de Versalles": ["Europa", "França", "París"],
        "La Guerra Freda": ["Europa"],
        "El fenomen del Paral·lel": ["Barcelona", "Raval"],
        "Els Pirineus en guerra": ["Catalunya", "Pirineus"],
        "La Xina de Mao": ["Xina", "República Popular de la Xina"],
        "Washington i Lincoln": ["Washington", "Estats Units"],
    }
    ITEMS = {
        name: name
        for name in [
            "Europa",
            "França",
            "París",
            "Barcelona",
            "Raval",
            "Catalunya",
            "Pirineus",
            "Xina",
            "República Popular de la Xina",
            "Washington",
            "Estats Units",
        ]
    }

    def seed(self, db_session):
        names = {name for tags in self.TAGS.values() for name in tags}
        categories = {
            name: Category(
                name=name,
                slug=Category.slugify_name(name),
                type=CategoryType.LOCATION,
            )
            for name in sorted(names)
        }
        episodes = {
            title: Episode(id=id, title=title)
            for id, title in enumerate(self.TAGS, start=1)
        }
        # The same name as a topic is no location.
        topic = Category(
            name="Europa", slug="europa-tema", type=CategoryType.TOPIC
        )
        db_session.add_all([*categories.values(), *episodes.values(), topic])
        db_session.flush()
        for title, tags in self.TAGS.items():
            for name in tags:
                db_session.add(
                    EpisodeCategory(
                        episode_id=episodes[title].id,
                        category_id=categories[name].id,
                    )
                )
        db_session.add(EpisodeCategory(episode_id=2, category_id=topic.id))
        db_session.commit()
        return {name: category.id for name, category in categories.items()}

    def run(self, db_session, monkeypatch, tmp_path, links=LINKS):
        monkeypatch.setattr(
            "maintenance.propose_location_containment.get_session",
            lambda: iter([db_session]),
        )
        links = {
            **links,
            # Points at the disambiguation page's item, which isn't a place.
            "Washington": [("P17", "Estats Units")],
        }
        path = tmp_path / "containment.csv"
        propose_location_containment(
            str(path),
            wikipedia=FakeWikipedia(self.ITEMS, disambiguation=["Washington"]),
            wikidata=FakeWikidata(links),
        )
        with open(path, newline="", encoding="utf-8-sig") as file:
            return list(csv.DictReader(file))

    def test_proposes_removing_the_broader_places(
        self, db_session, monkeypatch, tmp_path
    ):
        ids = self.seed(db_session)

        rows = self.run(db_session, monkeypatch, tmp_path)

        assert rows == [
            {
                "episode_id": "3",
                "episode": "El fenomen del Paral·lel",
                "remove_id": str(ids["Barcelona"]),
                "remove": "Barcelona",
                "because_of_id": str(ids["Raval"]),
                "because_of": "Raval",
                "path": "P131",
            },
            # Explained by París, which stays, not by França, which goes.
            {
                "episode_id": "1",
                "episode": "El Tractat de Versalles",
                "remove_id": str(ids["Europa"]),
                "remove": "Europa",
                "because_of_id": str(ids["París"]),
                "because_of": "París",
                "path": "P17/P30",
            },
            {
                "episode_id": "1",
                "episode": "El Tractat de Versalles",
                "remove_id": str(ids["França"]),
                "remove": "França",
                "because_of_id": str(ids["París"]),
                "because_of": "París",
                "path": "P17",
            },
        ]

    def test_reads_only_the_database(self, db_session, monkeypatch, tmp_path):
        self.seed(db_session)

        self.run(db_session, monkeypatch, tmp_path)

        assert (
            len(db_session.exec(EpisodeCategory.__table__.select()).all())
            == 13
        )
