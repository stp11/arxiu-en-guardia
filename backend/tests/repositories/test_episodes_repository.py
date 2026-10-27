from datetime import datetime

from sqlmodel import Session

from models import Category, CategoryType, Episode, EpisodeCategory
from repositories import EpisodesRepository


def embedding(x: float, y: float) -> list[float]:
    return [x, y] + [0.0] * 1534


class TestEpisodesRepository:
    def setup_method(self):
        self.episodes = [
            Episode(
                id=1,
                title="Episodi sobre Grecia",
                description="L'antiga Atenes i la democràcia.",
                published_at=datetime(2025, 1, 1),
            ),
            Episode(
                id=2,
                title="Episodi sobre la Guerra Civil",
                description="Els fronts de Catalunya durant el conflicte.",
                published_at=datetime(2025, 1, 2),
            ),
            Episode(
                id=3,
                title="Episodi sobre la Guerra del Vietnam",
                description="Saigon i l'ofensiva del Tet.",
                published_at=datetime(2025, 1, 3),
            ),
        ]

    def test_repository_search(self, db_session: Session):
        db_session.add_all(self.episodes)
        db_session.commit()
        repo = EpisodesRepository(session=db_session)

        query = repo.get_episodes_query(search="Guerra", order="asc")
        results = db_session.exec(query).all()

        assert len(results) == 2
        assert results[0].title == "Episodi sobre la Guerra Civil"
        assert results[1].title == "Episodi sobre la Guerra del Vietnam"

    def test_repository_search_matches_description(self, db_session: Session):
        db_session.add_all(self.episodes)
        db_session.commit()
        repo = EpisodesRepository(session=db_session)

        query = repo.get_episodes_query(search="Saigon", order="asc")
        results = db_session.exec(query).all()

        assert len(results) == 1
        assert results[0].title == "Episodi sobre la Guerra del Vietnam"

    def test_repository_search_takes_wildcards_literally(
        self, db_session: Session
    ):
        db_session.add_all(self.episodes)
        db_session.commit()
        repo = EpisodesRepository(session=db_session)

        for search in ["Guerra%Vietnam", "Gu_rra", "%"]:
            query = repo.get_episodes_query(search=search, order="asc")
            assert db_session.exec(query).all() == []

    def test_repository_ordering(self, db_session: Session):
        db_session.add_all(self.episodes)
        db_session.commit()
        repo = EpisodesRepository(session=db_session)

        query_desc = repo.get_episodes_query(search=None, order="desc")
        results_desc = db_session.exec(query_desc).all()

        query_asc = repo.get_episodes_query(search=None, order="asc")
        results_asc = db_session.exec(query_asc).all()

        assert results_desc[0].title == "Episodi sobre la Guerra del Vietnam"
        assert results_asc[0].title == "Episodi sobre Grecia"

    def test_repository_filter_categories(self, db_session: Session):
        categories = [
            Category(
                id=1,
                name="Guerra Civil",
                slug="guerra-civil",
                type=CategoryType.TOPIC,
            ),
            Category(
                id=2,
                name="Guerra del Vietnam",
                slug="guerra-del-vietnam",
                type=CategoryType.TOPIC,
            ),
        ]
        episode_categories = [
            EpisodeCategory(
                episode_id=self.episodes[0].id, category_id=categories[0].id
            ),
            EpisodeCategory(
                episode_id=self.episodes[1].id, category_id=categories[1].id
            ),
        ]
        db_session.add_all(self.episodes)
        db_session.add_all(categories)
        db_session.flush()
        db_session.add_all(episode_categories)
        db_session.commit()

        repo = EpisodesRepository(session=db_session)
        query = repo.get_episodes_query(
            search=None,
            order="asc",
            categories=["guerra-civil", "guerra-del-vietnam"],
        )
        results = db_session.exec(query).all()

        # Every selected category: no episode has both.
        assert results == []

        query = repo.get_episodes_query(
            search=None, order="asc", categories=["guerra-civil"]
        )
        results = db_session.exec(query).all()

        assert len(results) == 1
        assert results[0].title == "Episodi sobre Grecia"
        assert results[0].categories[0].name == "Guerra Civil"

    def test_repository_filter_categories_all_of_them(
        self, db_session: Session
    ):
        guerra = Category(
            name="Guerra", slug="guerra", type=CategoryType.TOPIC
        )
        democracia = Category(
            name="Democràcia", slug="democracia", type=CategoryType.TOPIC
        )
        catalunya = Category(
            name="Catalunya", slug="catalunya", type=CategoryType.LOCATION
        )
        self.episodes[0].categories = [democracia]
        self.episodes[1].categories = [guerra, democracia, catalunya]
        self.episodes[2].categories = [guerra]
        db_session.add_all(self.episodes)
        db_session.commit()
        repo = EpisodesRepository(session=db_session)

        def titles(categories: list[str]) -> list[str]:
            query = repo.get_episodes_query(
                search=None, order="asc", categories=categories
            )
            return [e.title for e in db_session.exec(query).all()]

        assert titles(["guerra"]) == [
            "Episodi sobre la Guerra Civil",
            "Episodi sobre la Guerra del Vietnam",
        ]
        # Every one of them, whatever their type, and an episode with
        # several comes back once.
        assert titles(["guerra", "democracia"]) == [
            "Episodi sobre la Guerra Civil"
        ]
        assert titles(["guerra", "democracia", "catalunya"]) == [
            "Episodi sobre la Guerra Civil"
        ]
        # An unknown slug among them is left out.
        assert titles(["guerra", "no-existeix"]) == [
            "Episodi sobre la Guerra Civil",
            "Episodi sobre la Guerra del Vietnam",
        ]

    def test_repository_filter_categories_ignores_unknown_slugs(
        self, db_session: Session
    ):
        db_session.add_all(self.episodes)
        db_session.commit()
        repo = EpisodesRepository(session=db_session)

        # A renamed or mistyped category in a link: as if it weren't there.
        query = repo.get_episodes_query(
            search=None, order="asc", categories=["no-existeix"]
        )
        assert len(db_session.exec(query).all()) == 3

    def test_repository_get_episode_by_id(self, db_session: Session):
        db_session.add_all(self.episodes)
        db_session.commit()
        repo = EpisodesRepository(session=db_session)

        episode = repo.get_episode_by_id(1)
        assert episode.title == "Episodi sobre Grecia"

    def test_repository_get_episode_by_id_not_found(self, db_session: Session):
        db_session.add_all(self.episodes)
        db_session.commit()
        repo = EpisodesRepository(session=db_session)

        episode = repo.get_episode_by_id(4)
        assert episode is None

    def test_repository_get_similar_episodes(self, db_session: Session):
        source = Episode(id=1, title="Font", embedding=embedding(1.0, 0.0))
        db_session.add_all(
            [
                source,
                Episode(id=2, title="Llunyà", embedding=embedding(0.1, 0.9)),
                Episode(id=3, title="Proper", embedding=embedding(0.9, 0.1)),
                Episode(id=4, title="Sense embedding"),
            ]
        )
        db_session.commit()
        repo = EpisodesRepository(session=db_session)

        results = repo.get_similar_episodes(source, limit=5)
        assert [e.id for e in results] == [3, 2]

        results = repo.get_similar_episodes(source, limit=1)
        assert [e.id for e in results] == [3]

    def test_repository_get_similar_episodes_weighs_shared_categories(
        self, db_session: Session
    ):
        almogavers = Category(id=1, name="Almogàvers", slug="almogavers")
        source = Episode(
            id=1,
            title="Font",
            embedding=embedding(1.0, 0.0),
            categories=[almogavers],
        )
        db_session.add_all(
            [
                source,
                Episode(id=2, title="Proper", embedding=embedding(0.9, 0.1)),
                Episode(
                    id=3,
                    title="Mateixa categoria",
                    embedding=embedding(0.8, 0.2),
                    categories=[almogavers],
                ),
                Episode(id=4, title="Llunyà", embedding=embedding(0.1, 0.9)),
            ]
        )
        db_session.commit()
        repo = EpisodesRepository(session=db_session)

        results = repo.get_similar_episodes(source, limit=5)
        assert [e.id for e in results] == [3, 2, 4]

    def test_repository_get_similar_episodes_rarer_categories_weigh_more(
        self, db_session: Session
    ):
        franquisme = Category(id=1, name="Franquisme", slug="franquisme")
        maquis = Category(id=2, name="Maquis", slug="maquis")
        source = Episode(
            id=1,
            title="Font",
            embedding=embedding(1.0, 0.0),
            categories=[franquisme, maquis],
        )
        db_session.add_all(
            [
                source,
                Episode(
                    id=2,
                    title="Comuna",
                    embedding=embedding(0.9, 0.1),
                    categories=[franquisme],
                ),
                Episode(
                    id=3,
                    title="Rara",
                    embedding=embedding(0.9, 0.1),
                    categories=[maquis],
                ),
                *[
                    Episode(
                        id=id,
                        title="Franquisme",
                        embedding=embedding(0.1, 0.9),
                        categories=[franquisme],
                    )
                    for id in (4, 5, 6)
                ],
            ]
        )
        db_session.commit()
        repo = EpisodesRepository(session=db_session)

        results = repo.get_similar_episodes(source, limit=2)
        assert [e.id for e in results] == [3, 2]
