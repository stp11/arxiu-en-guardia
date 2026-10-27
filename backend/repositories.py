from abc import ABC, abstractmethod

from sqlalchemy import (
    ColumnElement,
    Float,
    Select,
    Subquery,
    case,
    cast,
    func,
    or_,
)
from sqlalchemy.orm import defer, selectinload
from sqlmodel import Session, select

from models import (
    Category,
    CategoryCount,
    CategoryType,
    Episode,
    EpisodeCategory,
    EpisodeWikipediaArticle,
    LocationStats,
    LocationWithCount,
    WikipediaArticle,
)

# How much sharing categories counts for similar episodes, next to the
# vectors' cosine similarity. Both are 0 to 1: at 0.2, sharing every category
# is worth as much as a vector 0.2 closer.
CATEGORY_WEIGHT = 0.2


def episode_filters(
    search: str | None, categories: list[str]
) -> list[ColumnElement[bool]]:
    """
    The conditions on Episode for the list's search and categories.
    """
    filters = []

    if search and search.strip():
        # Escaped, so % and _ are matched as typed, not as wildcards.
        search_term = search.strip()
        filters.append(
            or_(
                Episode.title.icontains(search_term, autoescape=True),
                Episode.description.icontains(search_term, autoescape=True),
            )
        )

    # Every selected category: Guerra and Democràcia and Catalunya. An
    # episode has each category once, so it matches when it has as many of
    # them as are selected. Unknown slugs are left out of both counts, and
    # when none is known there's nothing to filter by. A subquery, not a
    # join, so an episode comes back once.
    if len(categories) > 0:
        selected = Category.slug.in_(categories)
        known = (
            select(func.count()).select_from(Category).where(selected)
        ).scalar_subquery()
        matching = (
            select(EpisodeCategory.episode_id)
            .join(Category, Category.id == EpisodeCategory.category_id)
            .where(selected)
            .group_by(EpisodeCategory.episode_id)
            .having(func.count() == known)
        )
        filters.append(or_(known == 0, Episode.id.in_(matching)))

    return filters


class ICategoriesRepository(ABC):
    @abstractmethod
    def get_all_categories(self) -> list[Category]:
        pass

    @abstractmethod
    def get_categories_query(self, type: CategoryType) -> Select:
        pass

    @abstractmethod
    def get_category_counts(
        self, search: str | None, categories: list[str]
    ) -> list[CategoryCount]:
        pass

    @abstractmethod
    def get_locations(self) -> list[LocationWithCount]:
        pass

    @abstractmethod
    def get_location_stats(self) -> LocationStats:
        pass

    @abstractmethod
    def get_or_create_category(
        self, name: str, type: CategoryType
    ) -> Category:
        pass

    @abstractmethod
    def map_category_type(self, type: str) -> CategoryType | None:
        pass


class CategoriesRepository(ICategoriesRepository):
    def __init__(self, session: Session):
        self.db_session = session

    def get_all_categories(self) -> list[Category]:
        return self.db_session.exec(select(Category)).all()

    def get_categories_query(self, type: CategoryType) -> Select:
        # Counted in one pass over the links, not one per category, and the
        # inner join leaves out the categories without episodes.
        return (
            select(
                Category, func.count(EpisodeCategory.episode_id).label("count")
            )
            .join(EpisodeCategory)
            .where(Category.type == type)
            .group_by(Category.id)
            .order_by(Category.name)
        )

    def get_category_counts(
        self, search: str | None, categories: list[str]
    ) -> list[CategoryCount]:
        # How many episodes the list would show with each category added to
        # the filters: of those it shows now, the ones with that category.
        # Those with none are left out; most first.
        matching = select(Episode.id).where(
            *episode_filters(search, categories)
        )
        counts = (
            select(Category.slug, func.count(EpisodeCategory.episode_id))
            .join(EpisodeCategory)
            .where(EpisodeCategory.episode_id.in_(matching))
            .group_by(Category.slug)
        )
        return sorted(
            (
                CategoryCount(slug=slug, count=count)
                for slug, count in self.db_session.exec(counts).all()
            ),
            key=lambda c: (-c.count, c.slug),
        )

    def get_locations(self) -> list[LocationWithCount]:
        rows = self.db_session.exec(
            self._on_map(
                select(
                    Category.id,
                    Category.slug,
                    Category.name,
                    Category.latitude,
                    Category.longitude,
                    func.count(EpisodeCategory.episode_id).label("count"),
                )
            )
            .group_by(Category.id)
            .order_by(Category.name)
        ).all()
        return [LocationWithCount(**row._mapping) for row in rows]

    def get_location_stats(self) -> LocationStats:
        on_map = self._on_map(
            select(func.count(EpisodeCategory.episode_id.distinct()))
        )
        total = select(func.count(Episode.id))
        episodes, total = self.db_session.exec(
            select(on_map.scalar_subquery(), total.scalar_subquery())
        ).one()
        return LocationStats(episodes=episodes, total=total)

    @staticmethod
    def _on_map(query: Select) -> Select:
        # The places on the map: those with coordinates and episodes.
        return (
            query.select_from(Category)
            .join(EpisodeCategory)
            .where(Category.type == CategoryType.LOCATION)
            .where(Category.latitude.is_not(None))
            .where(Category.longitude.is_not(None))
        )

    def get_or_create_category(
        self, name: str, type: CategoryType
    ) -> Category:
        slug = Category.slugify_name(name)
        category = self.db_session.exec(
            select(Category).where(Category.slug == slug)
        ).first()

        if not category:
            category = Category(name=name, slug=slug, type=type)
            self.db_session.add(category)
            self.db_session.flush()

        return category

    def map_category_type(self, type: str) -> CategoryType | None:
        if type == "temàtica":
            return CategoryType.TOPIC
        elif type == "època":
            return CategoryType.TIME_PERIOD
        elif type == "personatges":
            return CategoryType.CHARACTER
        elif type == "localització":
            return CategoryType.LOCATION
        else:
            return None


class IEpisodesRepository(ABC):
    @abstractmethod
    def get_episode_by_id(self, id: int) -> Episode | None:
        pass

    @abstractmethod
    def get_episodes_query(
        self, search: str | None, order: str, categories: list[str] = []
    ) -> Select:
        pass

    @abstractmethod
    def save_episode(self, episode: Episode) -> Episode:
        pass

    @abstractmethod
    def link_episode_to_category(
        self, episode_id: int, category_id: int
    ) -> None:
        pass

    @abstractmethod
    def link_episode_to_article(
        self, episode_id: int, article_id: int
    ) -> None:
        pass

    @abstractmethod
    def get_similar_episodes(
        self, episode: Episode, limit: int
    ) -> list[Episode]:
        pass


UPSTREAM_EPISODE_FIELDS = (
    "title",
    "slug",
    "description",
    "published_at",
    "image_url",
)


class EpisodesRepository(IEpisodesRepository):
    def __init__(self, session: Session):
        self.db_session = session

    def get_episodes_query(
        self, search: str | None, order: str, categories: list[str] = []
    ) -> Select:
        # The list doesn't show the vectors, which are most of each row.
        query = select(Episode).options(
            defer(Episode.embedding), selectinload(Episode.categories)
        )

        if order == "desc":
            query = query.order_by(Episode.published_at.desc())
        else:
            query = query.order_by(Episode.published_at.asc())

        return query.where(*episode_filters(search, categories))

    def get_episode_by_id(self, id: int) -> Episode:
        return self.db_session.exec(
            select(Episode)
            .where(Episode.id == id)
            .options(
                selectinload(Episode.categories),
                selectinload(Episode.wikipedia_articles),
            )
        ).first()

    def save_episode(self, episode: Episode) -> Episode:
        existing = self.db_session.get(Episode, episode.id)
        if existing is None:
            self.db_session.add(episode)
            return episode
        # Only what the feed provides; the vector and the linking state are
        # worked out here, and a merge would reset them to their defaults.
        for field in UPSTREAM_EPISODE_FIELDS:
            setattr(existing, field, getattr(episode, field))
        return existing

    def link_episode_to_category(
        self, episode_id: int, category_id: int
    ) -> None:
        existing = self.db_session.exec(
            select(EpisodeCategory).where(
                EpisodeCategory.episode_id == episode_id,
                EpisodeCategory.category_id == category_id,
            )
        ).first()

        if not existing:
            link = EpisodeCategory(
                episode_id=episode_id, category_id=category_id
            )
            self.db_session.add(link)

    def link_episode_to_article(
        self, episode_id: int, article_id: int
    ) -> None:
        existing = self.db_session.exec(
            select(EpisodeWikipediaArticle).where(
                EpisodeWikipediaArticle.episode_id == episode_id,
                EpisodeWikipediaArticle.article_id == article_id,
            )
        ).first()

        if not existing:
            link = EpisodeWikipediaArticle(
                episode_id=episode_id, article_id=article_id
            )
            self.db_session.add(link)

    def get_similar_episodes(
        self, episode: Episode, limit: int
    ) -> list[Episode]:
        # Categories are curated in the admin, and count as soon as they're
        # edited, while vectors wait to be regenerated.
        categories = self._category_similarity(episode)
        return self.db_session.exec(
            select(Episode)
            .outerjoin(categories, categories.c.episode_id == Episode.id)
            .where(Episode.embedding.isnot(None))
            .where(Episode.id != episode.id)
            .options(selectinload(Episode.categories))
            .order_by(
                Episode.embedding.cosine_distance(episode.embedding)
                - CATEGORY_WEIGHT * func.coalesce(categories.c.similarity, 0.0)
            )
            .limit(limit)
        ).all()

    def _category_similarity(self, episode: Episode) -> Subquery:
        """
        The cosine similarity, 0 to 1, of each episode's categories to the
        episode's, each one weighing more the fewer episodes it has (tf-idf):
        sharing Jaume I says more than sharing Franquisme.
        """
        episodes = select(func.count()).select_from(Episode).scalar_subquery()
        weights = (
            select(
                EpisodeCategory.category_id,
                func.ln(cast(episodes, Float) / func.count()).label("weight"),
            )
            .group_by(EpisodeCategory.category_id)
            .subquery()
        )
        squared = weights.c.weight * weights.c.weight
        shared = weights.c.category_id.in_(
            [category.id for category in episode.categories]
        )
        norm = (
            select(func.sqrt(func.sum(squared))).where(shared)
        ).scalar_subquery()

        # An episode whose categories every episode has weighs 0, and
        # divides by NULL rather than by zero.
        return (
            select(
                EpisodeCategory.episode_id,
                (
                    func.sum(case((shared, squared), else_=0.0))
                    / func.nullif(func.sqrt(func.sum(squared)) * norm, 0)
                ).label("similarity"),
            )
            .join(
                weights, weights.c.category_id == EpisodeCategory.category_id
            )
            .group_by(EpisodeCategory.episode_id)
            .subquery()
        )


class IWikipediaArticlesRepository(ABC):
    @abstractmethod
    def get_or_create_article(self, title: str, url: str) -> WikipediaArticle:
        pass


class WikipediaArticlesRepository(IWikipediaArticlesRepository):
    def __init__(self, session: Session):
        self.db_session = session

    def get_or_create_article(self, title: str, url: str) -> WikipediaArticle:
        article = self.db_session.exec(
            select(WikipediaArticle).where(WikipediaArticle.title == title)
        ).first()

        if not article:
            article = WikipediaArticle(title=title, url=url)
            self.db_session.add(article)
            self.db_session.flush()

        return article
