import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from fastapi import Request
from slugify import slugify
from sqladmin import ModelView
from sqlalchemy import Select
from sqlmodel import TEXT, Column, DateTime, Field, Relationship, SQLModel


class EpisodeCategory(SQLModel, table=True):
    episode_id: int | None = Field(
        default=None, foreign_key="episode.id", primary_key=True
    )
    category_id: int | None = Field(
        default=None, foreign_key="category.id", primary_key=True
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


class EpisodeBase(SQLModel):
    id: int
    title: str
    slug: str | None
    description: str | None
    published_at: datetime | None
    image_url: str | None


class EpisodeWithCategories(EpisodeBase):
    categories: list[CategoryBase] = []


class Episode(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    slug: str | None = None
    description: str | None = Field(default=None, sa_column=Column(TEXT))
    published_at: datetime | None = Field(default=None, index=True)
    image_url: str | None = None

    categories: list[Category] = Relationship(
        back_populates="episodes",
        link_model=EpisodeCategory,
        sa_relationship_kwargs={
            "order_by": "Category.type, Category.name",
            "lazy": "selectin",
        },
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
    created_at: datetime | None = Field(
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
        Episode.published_at,
    ]
    column_formatters = {
        Episode.categories: lambda model, attribute: (
            [category.name for category in model.categories]
            if model.categories
            else "No hi ha categories"
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
    ]

    form_columns = [
        Episode.title,
        Episode.description,
        Episode.categories,
    ]

    # Multi-select as tags
    form_ajax_refs = {
        "categories": {
            "fields": ("name",),
        }
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
    }

    page_size = 25


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
