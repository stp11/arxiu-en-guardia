from datetime import datetime

from commands.geocode_locations import geocode_locations
from models import Category, CategoryType
from wikipedia import Article


class FakeWikipedia:
    COORDINATES = {"Montserrat": (41.6, 1.8), "Catalunya": (41.8, 1.5)}

    def lookup(self, titles):
        return {
            title: (
                Article(
                    title,
                    f"https://ca.wikipedia.org/wiki/{title}",
                    coordinates=self.COORDINATES[title],
                )
                if title in self.COORDINATES
                else None
            )
            for title in titles
        }


CHECKED = datetime(2026, 10, 20, 17, 0)


def location(id: int, name: str, **kwargs) -> Category:
    return Category(
        id=id,
        name=name,
        slug=Category.slugify_name(name),
        type=CategoryType.LOCATION,
        **kwargs,
    )


class TestGeocodeLocations:
    def seed(self, db_session):
        db_session.add_all(
            [
                location(1, "Montserrat"),
                location(2, "Villa Diodati"),
                # Kept off the map in the admin.
                location(3, "Catalunya", geocoded_at=CHECKED),
                # Placed by hand.
                location(
                    4,
                    "Muntanya de Montjuïc",
                    latitude=41.36,
                    longitude=2.16,
                    geocoded_at=CHECKED,
                ),
                Category(
                    id=5,
                    name="Catalunya",
                    slug="catalunya-tema",
                    type=CategoryType.TOPIC,
                ),
            ]
        )
        db_session.commit()

    def run(self, db_session, monkeypatch, **kwargs):
        monkeypatch.setattr(
            "commands.geocode_locations.WikipediaClient", FakeWikipedia
        )
        monkeypatch.setattr(
            "commands.geocode_locations.get_session",
            lambda: iter([db_session]),
        )

        geocode_locations(**kwargs)

        db_session.expire_all()

    def place(self, db_session, id: int):
        category = db_session.get(Category, id)
        return category.latitude, category.longitude, category.geocoded_at

    def test_places_only_locations_not_looked_up_yet(
        self, db_session, monkeypatch
    ):
        self.seed(db_session)

        self.run(db_session, monkeypatch)

        latitude, longitude, geocoded_at = self.place(db_session, 1)
        assert (latitude, longitude) == (41.6, 1.8)
        assert geocoded_at > CHECKED
        # Not found, and not looked up again.
        latitude, longitude, geocoded_at = self.place(db_session, 2)
        assert (latitude, longitude) == (None, None)
        assert geocoded_at > CHECKED
        # The admin's edits stay.
        assert self.place(db_session, 3) == (None, None, CHECKED)
        assert self.place(db_session, 4) == (41.36, 2.16, CHECKED)
        assert self.place(db_session, 5) == (None, None, None)

    def test_dry_run_saves_nothing(self, db_session, monkeypatch):
        self.seed(db_session)

        self.run(db_session, monkeypatch, dry_run=True)

        assert self.place(db_session, 1) == (None, None, None)
        assert self.place(db_session, 2) == (None, None, None)
