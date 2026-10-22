from abc import ABC, abstractmethod

from sqlalchemy import Select, func, or_
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from models import (
    Category,
    CategoryType,
    Episode,
    EpisodeCategory,
    EpisodeWikipediaArticle,
    WikipediaArticle,
)


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


class EpisodesRepository(IEpisodesRepository):
    def __init__(self, session: Session):
        self.db_session = session

    def get_episodes_query(
        self, search: str | None, order: str, categories: list[str] = []
    ) -> Select:
        query = select(Episode).options(selectinload(Episode.categories))

        if search and search.strip():
            search_term = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Episode.title.ilike(search_term),
                    Episode.description.ilike(search_term),
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
        return self.db_session.merge(episode)

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
        return self.db_session.exec(
            select(Episode)
            .where(Episode.embedding.isnot(None))
            .where(Episode.id != episode.id)
            .options(selectinload(Episode.categories))
            .order_by(Episode.embedding.cosine_distance(episode.embedding))
            .limit(limit)
        ).all()


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
