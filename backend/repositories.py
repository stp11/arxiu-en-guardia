from abc import ABC, abstractmethod

from sqlalchemy import Float, Select, Subquery, case, cast, func, or_
from sqlalchemy.orm import defer, selectinload
from sqlmodel import Session, select

from models import (
    Category,
    CategoryType,
    Episode,
    EpisodeCategory,
    EpisodeWikipediaArticle,
    WikipediaArticle,
)

# How much sharing categories counts for similar episodes, next to the
# vectors' cosine similarity. Both are 0 to 1: at 0.2, sharing every category
# is worth as much as a vector 0.2 closer.
CATEGORY_WEIGHT = 0.2


class ICategoriesRepository(ABC):
    @abstractmethod
    def get_all_categories(self) -> list[Category]:
        pass

    @abstractmethod
    def get_categories_query(self, type: CategoryType) -> Select:
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

        if search and search.strip():
            # Escaped, so % and _ are matched as typed, not as wildcards.
            search_term = search.strip()
            query = query.where(
                or_(
                    Episode.title.icontains(search_term, autoescape=True),
                    Episode.description.icontains(
                        search_term, autoescape=True
                    ),
                )
            )

        if order == "desc":
            query = query.order_by(Episode.published_at.desc())
        else:
            query = query.order_by(Episode.published_at.asc())

        if len(categories) > 0:
            query = (
                query.join(EpisodeCategory)
                .join(Category)
                .where(Category.slug.in_(categories))
            )

        return query

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
