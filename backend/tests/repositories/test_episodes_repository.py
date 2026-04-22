from datetime import datetime

from sqlmodel import Session

from models import Category, CategoryType, Episode, EpisodeCategory
from repositories import EpisodesRepository


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
        db_session.add_all(episode_categories)
        db_session.add_all(categories)
        db_session.commit()

        repo = EpisodesRepository(session=db_session)
        query = repo.get_episodes_query(
            search=None,
            order="asc",
            categories=["guerra-civil", "guerra-del-vietnam"],
        )
        results = db_session.exec(query).all()

        assert len(results) == 2
        assert results[0].title == "Episodi sobre Grecia"
        assert results[0].categories[0].name == "Guerra Civil"
        assert results[1].title == "Episodi sobre la Guerra Civil"
        assert results[1].categories[0].name == "Guerra del Vietnam"

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
