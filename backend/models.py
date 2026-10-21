import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from fastapi import Request
from fastapi.responses import RedirectResponse
from pgvector.sqlalchemy import Vector
from pydantic import NaiveDatetime
from slugify import slugify
from sqladmin import ModelView, action
from sqlalchemy import Select
from sqlmodel import (
    TEXT,
    Column,
    DateTime,
    Field,
    Relationship,
    SQLModel,
    select,
)

from tasks.episode_tasks import (
    generate_embeddings_task,
    link_wikipedia_articles_task,
)
from wikipedia import WikipediaClient


class EpisodeCategory(SQLModel, table=True):
    episode_id: int | None = Field(
        default=None, foreign_key="episode.id", primary_key=True
    )
    category_id: int | None = Field(
        default=None, foreign_key="category.id", primary_key=True
    )


class EpisodeWikipediaArticle(SQLModel, table=True):
    episode_id: int | None = Field(
        default=None, foreign_key="episode.id", primary_key=True
    )
    article_id: int | None = Field(
        default=None, foreign_key="wikipediaarticle.id", primary_key=True
    )


class CategoryType(str, Enum):
    TOPIC = "topic"
    LOCATION = "location"
    CHARACTER = "character"
    TIME_PERIOD = "time_period"


class CategoryBase(SQLModel):
    id: int
    slug: str
    name: str
    type: CategoryType | None


class CategoryWithCount(CategoryBase):
    count: int


class Category(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(unique=True, index=True)
    name: str = Field(index=True)
    type: CategoryType | None = Field(index=True)

    episodes: list["Episode"] = Relationship(
        back_populates="categories", link_model=EpisodeCategory
    )

    def __str__(self) -> str:
        return self.name

    @staticmethod
    def slugify_name(name: str) -> str:
        return slugify(name)


class WikipediaArticle(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(unique=True, index=True)
    url: str

    episodes: list["Episode"] = Relationship(
        back_populates="wikipedia_articles",
        link_model=EpisodeWikipediaArticle,
    )

    def __str__(self) -> str:
        return self.title


class EpisodeBase(SQLModel):
    id: int
    title: str
    slug: str | None
    description: str | None
    published_at: datetime | None
    image_url: str | None


class EpisodeWithCategories(EpisodeBase):
    categories: list[CategoryBase] = []


class WikipediaArticleBase(SQLModel):
    title: str
    url: str


class EpisodeDetail(EpisodeWithCategories):
    wikipedia_articles: list[WikipediaArticleBase] = []


class Episode(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    slug: str | None = None
    description: str | None = Field(default=None, sa_column=Column(TEXT))
    published_at: NaiveDatetime | None = Field(default=None, index=True)
    image_url: str | None = None
    embedding: list[float] | None = Field(
        default=None, sa_column=Column(Vector(1536))
    )
    # When the Wikipedia linking job last looked at the episode, so it
    # doesn't run again, nor undo the admin's edits, every week.
    wikipedia_checked_at: NaiveDatetime | None = None

    categories: list[Category] = Relationship(
        back_populates="episodes",
        link_model=EpisodeCategory,
        sa_relationship_kwargs={
            "order_by": "Category.type, Category.name",
            "lazy": "selectin",
        },
    )
    wikipedia_articles: list[WikipediaArticle] = Relationship(
        back_populates="episodes",
        link_model=EpisodeWikipediaArticle,
        sa_relationship_kwargs={"order_by": "WikipediaArticle.title"},
    )

    def __str__(self) -> str:
        return self.title


class IngestionPosition(SQLModel, table=True):
    id: int | None = Field(default=1, primary_key=True)
    last_episode_id: int | None = None
    updated_at: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime, onupdate=datetime.now(timezone.utc)),
    )


class Users(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False)
    created_at: NaiveDatetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, password: str) -> bool:
        """Verify a password against the stored hash"""
        return self.password_hash == self.hash_password(password)

    def __str__(self) -> str:
        return self.username


# Admin view
class EpisodeWithoutCategoriesFilter:
    """Custom filter to show episodes without categories"""

    def __init__(
        self,
        column: Any = None,
        title: str | None = None,
        parameter_name: str | None = None,
    ):
        self.column = column
        self.title = title or "Episodis"
        self.parameter_name = parameter_name or "has_categories"

    async def lookups(
        self, request: Request, model: Any, run_query: Callable[[Select], Any]
    ) -> list[tuple[str, str]]:
        """Return filter options"""
        return [
            ("", "Tots"),
            ("no", "Sense categories"),
            ("yes", "Amb categories"),
        ]

    async def get_filtered_query(
        self, query: Select, value: Any, model: Any
    ) -> Select:
        """Apply the filter to the query"""
        if value == "":
            return query
        elif value == "no":
            return query.outerjoin(EpisodeCategory).where(
                EpisodeCategory.episode_id.is_(None)
            )
        elif value == "yes":
            return query.join(EpisodeCategory).distinct()
        return query


class EpisodeAdmin(ModelView, model=Episode):
    name_plural = "Episodis"
    can_create = False
    can_edit = True
    can_delete = True
    can_view_details = True

    column_list = [
        Episode.id,
        Episode.title,
        Episode.categories,
        Episode.wikipedia_articles,
        Episode.published_at,
    ]
    column_formatters = {
        Episode.categories: lambda model, attribute: (
            [category.name for category in model.categories]
            if model.categories
            else "No hi ha categories"
        ),
        # "Pendent" marks where the last Wikipedia linking batch stopped.
        Episode.wikipedia_articles: lambda model, attribute: (
            [article.title for article in model.wikipedia_articles]
            if model.wikipedia_articles
            else (
                "No hi ha articles"
                if model.wikipedia_checked_at
                else "Pendent"
            )
        ),
    }
    list_template = "sqladmin/custom_list.html"
    details_template = "sqladmin/custom_details.html"
    column_searchable_list = [Episode.title]
    column_sortable_list = [Episode.published_at]
    column_default_sort = [(Episode.published_at, True)]
    column_filters = [EpisodeWithoutCategoriesFilter()]
    column_details_list = [
        Episode.title,
        Episode.description,
        Episode.categories,
        Episode.wikipedia_articles,
        Episode.wikipedia_checked_at,
    ]

    form_columns = [
        Episode.title,
        Episode.description,
        Episode.categories,
        Episode.wikipedia_articles,
    ]

    # Multi-select as tags
    form_ajax_refs = {
        "categories": {
            "fields": ("name",),
        },
        "wikipedia_articles": {
            "fields": ("title",),
        },
    }

    form_widget_args = {
        "description": {
            "rows": 8,
            "readonly": True,
        },
        "title": {
            "readonly": True,
        },
        "categories": {
            "multiple": True,
        },
        "wikipedia_articles": {
            "multiple": True,
        },
    }

    page_size = 25

    # The confirmations read for one episode, from its page, or for many.
    @action(
        name="relink-wikipedia",
        label="Busca articles a la Viquipèdia",
        confirmation_message=(
            "Els articles de la Viquipèdia se substituiran pels que es trobin "
            "ara. Recarrega la pàgina d'aquí a uns segons per veure'ls."
        ),
    )
    async def relink_wikipedia(self, request: Request) -> RedirectResponse:
        ids = self._selected_ids(request)
        with self.session_maker() as session:
            episodes = (
                session.execute(select(Episode).where(Episode.id.in_(ids)))
                .scalars()
                .all()
            )
            for episode in episodes:
                episode.wikipedia_articles = []
                episode.wikipedia_checked_at = None
            session.commit()

        # Queued once they're cleared: the linking skips episodes that still
        # look checked. The worker searches while the page reloads.
        link_wikipedia_articles_task.delay(episode_ids=ids)
        return self._go_back(request)

    @action(
        name="regenerate-embeddings",
        label="Regenera els vectors",
        confirmation_message=(
            "Els vectors, amb què es trien els episodis similars, es tornaran "
            "a calcular amb les categories actuals."
        ),
    )
    async def regenerate_embeddings(
        self, request: Request
    ) -> RedirectResponse:
        # Replaced in place: the episodes keep their vectors, and their
        # similar episodes, until the new ones are saved.
        generate_embeddings_task.delay(
            episode_ids=self._selected_ids(request), refresh=True
        )
        return self._go_back(request)

    def _selected_ids(self, request: Request) -> list[int]:
        return [
            int(pk)
            for pk in request.query_params.get("pks", "").split(",")
            if pk
        ]

    # To the list or the episode's page, wherever the action was run from.
    def _go_back(self, request: Request) -> RedirectResponse:
        referer = request.headers.get("Referer")
        return RedirectResponse(
            referer or request.url_for("admin:list", identity=self.identity),
            status_code=302,
        )


class CategoryWithoutEpisodesFilter:
    """Custom filter to show categories without episodes"""

    def __init__(
        self,
        column: Any = None,
        title: str | None = None,
        parameter_name: str | None = None,
    ):
        self.column = column
        self.title = title or "Categories"
        self.parameter_name = parameter_name or "has_episodes"

    async def lookups(
        self, request: Request, model: Any, run_query: Callable[[Select], Any]
    ) -> list[tuple[str, str]]:
        """Return filter options"""
        return [
            ("", "Totes"),
            ("no", "Sense episodis"),
            ("yes", "Amb episodis"),
        ]

    async def get_filtered_query(
        self, query: Select, value: Any, model: Any
    ) -> Select:
        """Apply the filter to the query"""
        if value == "":
            return query
        elif value == "no":
            # Categories without episodes
            return query.outerjoin(EpisodeCategory).where(
                EpisodeCategory.category_id.is_(None)
            )
        elif value == "yes":
            # Categories with episodes
            return query.join(EpisodeCategory).distinct()
        return query


class CategoryAdmin(ModelView, model=Category):
    name_plural = "Categories"
    can_create = True
    can_edit = True
    can_delete = True
    can_view_details = True

    column_list = [Category.name, Category.type, Category.episodes]
    column_formatters = {
        Category.type: lambda model, attribute: (
            {
                CategoryType.TOPIC.value: "Temàtica",
                CategoryType.LOCATION.value: "Localització",
                CategoryType.CHARACTER.value: "Personatge",
                CategoryType.TIME_PERIOD.value: "Època",
            }.get(model.type.value if model.type else None, "")
        ),
        Category.episodes: lambda model, attribute: (
            model.episodes if model.episodes else "-"
        ),
    }
    list_template = "sqladmin/custom_list.html"
    details_template = "sqladmin/custom_details.html"
    column_searchable_list = [Category.name]
    column_sortable_list = [Category.name, Category.type]
    column_default_sort = [(Category.name, False)]
    column_filters = [CategoryWithoutEpisodesFilter()]
    column_details_list = [
        Category.name,
        Category.slug,
        Category.type,
        Category.episodes,
    ]

    form_columns = [Category.name, Category.type, Category.episodes]

    # Multi-select as tags
    form_ajax_refs = {
        "episodes": {
            "fields": ("title",),
        }
    }

    page_size = 50

    async def on_model_change(
        self, data: dict, model: Category, is_created: bool, request: Request
    ) -> None:
        name = (data.get("name") or getattr(model, "name", "")).strip()
        if name:
            slug = Category.slugify_name(name)
            from sqlmodel import select

            with self.session_maker() as session:
                existing = (
                    session.execute(
                        select(Category).where(Category.slug == slug)
                    )
                    .scalars()
                    .first()
                )

                if existing and (
                    getattr(model, "id", None) is None
                    or existing.id != model.id
                ):
                    raise ValueError(
                        "A category with this slug already exists."
                    )

            data["slug"] = slug


class WikipediaArticleAdmin(ModelView, model=WikipediaArticle):
    name_plural = "Articles de la Viquipèdia"
    can_create = True
    can_edit = True
    can_delete = True
    can_view_details = True

    column_list = [
        WikipediaArticle.title,
        WikipediaArticle.url,
        WikipediaArticle.episodes,
    ]
    column_formatters = {
        WikipediaArticle.episodes: lambda model, attribute: (
            model.episodes if model.episodes else "-"
        ),
    }
    list_template = "sqladmin/custom_list.html"
    details_template = "sqladmin/custom_details.html"
    column_searchable_list = [WikipediaArticle.title]
    column_sortable_list = [WikipediaArticle.title]
    column_default_sort = [(WikipediaArticle.title, False)]
    column_details_list = [
        WikipediaArticle.title,
        WikipediaArticle.url,
        WikipediaArticle.episodes,
    ]

    # The URL comes from Wikipedia when the title is saved.
    form_columns = [WikipediaArticle.title, WikipediaArticle.episodes]

    # Multi-select as tags
    form_ajax_refs = {
        "episodes": {
            "fields": ("title",),
        }
    }

    page_size = 50

    async def on_model_change(
        self,
        data: dict,
        model: WikipediaArticle,
        is_created: bool,
        request: Request,
    ) -> None:
        title = (data.get("title") or getattr(model, "title", "")).strip()
        article = WikipediaClient().lookup([title])[title]
        if article is None:
            raise ValueError(f'La Viquipèdia no té cap article "{title}".')
        if article.disambiguation:
            raise ValueError(
                f'"{article.title}" és una pàgina de desambiguació: '
                "tria'n l'article concret."
            )

        with self.session_maker() as session:
            existing = (
                session.execute(
                    select(WikipediaArticle).where(
                        WikipediaArticle.title == article.title
                    )
                )
                .scalars()
                .first()
            )
            if existing and existing.id != getattr(model, "id", None):
                raise ValueError(f'L\'article "{article.title}" ja existeix.')

        # A redirect's title is saved as the article it leads to.
        data["title"] = article.title
        data["url"] = article.url
