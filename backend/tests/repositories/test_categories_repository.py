from sqlmodel import Session

from models import Category, CategoryType, Episode, EpisodeCategory
from repositories import CategoriesRepository


class TestCategoriesRepository:
    def setup_method(self):
        self.categories = [
            Category(
                name="Antiga Grecia",
                slug="antiga-grecia",
                type=CategoryType.LOCATION,
            ),
            Category(
                name="Guerra Civil",
                slug="guerra-civil",
                type=CategoryType.TOPIC,
            ),
            Category(
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
        episodes = [
            Episode(id=1, title="Test Episode"),
            Episode(id=2, title="Another Episode"),
        ]
        unused = Category(name="Roma", slug="roma", type=CategoryType.LOCATION)
        db_session.add_all([*self.categories, unused, *episodes])
        db_session.flush()
        db_session.add_all(
            [
                EpisodeCategory(
                    episode_id=episode.id, category_id=self.categories[0].id
                )
                for episode in episodes
            ]
            + [
                EpisodeCategory(
                    episode_id=1, category_id=self.categories[1].id
                )
            ]
        )
        db_session.commit()
        repo = CategoriesRepository(session=db_session)

        query = repo.get_categories_query(CategoryType.LOCATION)
        assert query is not None

        # Roma has no episodes, so it's left out.
        results = db_session.exec(query).all()
        assert len(results) == 1
        category, count = results[0]
        assert category.name == "Antiga Grecia"
        assert count == 2

    def test_get_locations(self, db_session: Session):
        grecia, guerra, _ = self.categories
        grecia.latitude, grecia.longitude = 38.0, 23.7
        guerra.latitude, guerra.longitude = 40.4, -3.7
        roma = Category(
            name="Roma",
            slug="roma",
            type=CategoryType.LOCATION,
            latitude=41.9,
            longitude=12.5,
        )
        catalunya = Category(
            name="Catalunya", slug="catalunya", type=CategoryType.LOCATION
        )
        db_session.add_all(
            [
                *self.categories,
                roma,
                catalunya,
                Episode(
                    id=1,
                    title="Test Episode",
                    categories=[grecia, guerra, catalunya],
                ),
                Episode(id=2, title="Another Episode", categories=[grecia]),
            ]
        )
        db_session.commit()
        repo = CategoriesRepository(session=db_session)

        # Only places with coordinates and episodes: not the topic, nor
        # Roma, without episodes, nor Catalunya, kept off the map.
        assert [
            location.model_dump() for location in repo.get_locations()
        ] == [
            {
                "id": grecia.id,
                "slug": "antiga-grecia",
                "name": "Antiga Grecia",
                "latitude": 38.0,
                "longitude": 23.7,
                "count": 2,
            }
        ]

    def test_get_location_stats(self, db_session: Session):
        grecia, guerra, _ = self.categories
        grecia.latitude, grecia.longitude = 38.0, 23.7
        roma = Category(
            name="Roma",
            slug="roma",
            type=CategoryType.LOCATION,
            latitude=41.9,
            longitude=12.5,
        )
        catalunya = Category(
            name="Catalunya", slug="catalunya", type=CategoryType.LOCATION
        )
        db_session.add_all(
            [
                Episode(
                    id=1, title="Roma i Grècia", categories=[roma, grecia]
                ),
                Episode(id=2, title="Grècia", categories=[grecia]),
                Episode(id=3, title="Catalunya", categories=[catalunya]),
                Episode(id=4, title="Sense lloc", categories=[guerra]),
            ]
        )
        db_session.commit()
        repo = CategoriesRepository(session=db_session)

        # The first episode is in two places, but counts once; the third's
        # only place is off the map.
        assert repo.get_location_stats().model_dump() == {
            "episodes": 2,
            "total": 4,
        }

    def test_get_category_counts(self, db_session: Session):
        grecia, guerra, frances = self.categories
        db_session.add_all(
            [
                Episode(id=1, title="Atenes en guerra", categories=[grecia]),
                Episode(id=2, title="Esparta", categories=[grecia, guerra]),
                Episode(id=3, title="Bruc", categories=[frances]),
            ]
        )
        db_session.commit()
        repo = CategoriesRepository(session=db_session)

        def counts(search: str | None, categories: list[str]):
            return [
                (c.slug, c.count)
                for c in repo.get_category_counts(search, categories)
            ]

        # Most first, then by slug.
        assert counts(None, []) == [
            ("antiga-grecia", 2),
            ("guerra-civil", 1),
            ("guerra-del-frances", 1),
        ]
        # Only the episodes that match the search.
        assert counts("guerra", []) == [("antiga-grecia", 1)]
        # A topic selected: everything narrows to its episodes, and the
        # other topic, in none of them, is left out.
        assert counts(None, ["guerra-civil"]) == [
            ("antiga-grecia", 1),
            ("guerra-civil", 1),
        ]
        # A place selected: the Guerra del Francès isn't in it, so it's
        # left out.
        assert counts(None, ["antiga-grecia"]) == [
            ("antiga-grecia", 2),
            ("guerra-civil", 1),
        ]

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
