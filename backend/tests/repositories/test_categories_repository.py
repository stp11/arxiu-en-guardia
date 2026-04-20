from sqlmodel import Session

from models import Category, CategoryType, Episode, EpisodeCategory
from repositories import CategoriesRepository


class TestCategoriesRepository:
    def setup_method(self):
        self.categories = [
            Category(
                id=1,
                name="Antiga Grecia",
                slug="antiga-grecia",
                type=CategoryType.LOCATION,
            ),
            Category(
                id=2,
                name="Guerra Civil",
                slug="guerra-civil",
                type=CategoryType.TOPIC,
            ),
            Category(
                id=3,
                name="Guerra del Francès",
                slug="guerra-del-frances",
                type=CategoryType.TOPIC,
            ),
        ]

    def test_get_all_categories(self, db_session: Session):
        db_session.add_all(self.categories)
        db_session.commit()
        repo = CategoriesRepository(session=db_session)

        results = repo.get_all_categories()

        assert len(results) == 3

    def test_get_categories_query(self, db_session: Session):
        episode = Episode(id=1, title="Test Episode")
        episode_category = EpisodeCategory(
            episode_id=episode.id, category_id=self.categories[0].id
        )
        db_session.add_all(self.categories)
        db_session.add(episode)
        db_session.add(episode_category)
        db_session.commit()
        repo = CategoriesRepository(session=db_session)

        query = repo.get_categories_query(CategoryType.LOCATION)
        assert query is not None

        results = db_session.exec(query).all()
        assert len(results) == 1
        category, count = results[0]
        assert category.name == "Antiga Grecia"
        assert count == 1

    def test_get_or_create_category(self, db_session: Session):
        db_session.add_all(self.categories)
        db_session.commit()
        repo = CategoriesRepository(session=db_session)

        # Create a new category
        result = repo.get_or_create_category(
            name="Guerra dels Segadors", type=CategoryType.TOPIC
        )
        assert result.name == "Guerra dels Segadors"
        assert result.type == CategoryType.TOPIC

        # Get an existing category
        result = repo.get_or_create_category(
            name="Guerra del Francès", type=CategoryType.TOPIC
        )
        assert result.name == "Guerra del Francès"
        assert result.type == CategoryType.TOPIC

        results = repo.get_all_categories()
        assert len(results) == 4

    def test_map_category_type(self, db_session: Session):
        db_session.add_all(self.categories)
        db_session.commit()
        repo = CategoriesRepository(session=db_session)

        result = repo.map_category_type(type="temàtica")
        assert result == CategoryType.TOPIC

        result = repo.map_category_type(type="època")
        assert result == CategoryType.TIME_PERIOD

        result = repo.map_category_type(type="personatges")
        assert result == CategoryType.CHARACTER

        result = repo.map_category_type(type="localització")
        assert result == CategoryType.LOCATION
