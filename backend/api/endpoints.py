from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi_pagination import Page
from fastapi_pagination.customization import CustomizedPage, UseParamsFields
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import Session

from database import get_session
from dependencies import get_categories_service, get_episodes_service
from models import CategoryType, CategoryWithCount, EpisodeWithCategories
from services import CategoriesService, EpisodesService

router = APIRouter()


@router.get(
    "/episodes", tags=["episodis"], response_model=Page[EpisodeWithCategories]
)
def get_episodes(
    service: EpisodesService = Depends(get_episodes_service),
    # We still need the session for the pagination function
    session: Session = Depends(get_session),
    search: str = "",
    order: str = "desc",
    categories: str = Query(
        "", description="Comma-separated list of category slugs"
    ),
):
    query = service.get_episodes_query(
        search=search, order=order, categories=categories
    )
    return paginate(session, query)


@router.get(
    "/episodes/{id}", tags=["episodis"], response_model=EpisodeWithCategories
)
def get_episode(
    id: int = Path(..., description="Episode ID"),
    service: EpisodesService = Depends(get_episodes_service),
):
    episode = service.get_episode_by_id(id)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    return episode


CustomPage = CustomizedPage[
    Page,
    UseParamsFields(
        size=Query(100, ge=1, le=1000),
    ),
]


@router.get(
    "/categories",
    tags=["categories"],
    response_model=CustomPage[CategoryWithCount],
)
def get_categories(
    service: CategoriesService = Depends(get_categories_service),
    session: Session = Depends(get_session),
    type: CategoryType = Query("", description="Category type"),
):
    def transform(rows):
        return [
            CategoryWithCount(
                id=cat.id,
                slug=cat.slug,
                name=cat.name,
                type=cat.type,
                count=count,
            )
            for cat, count in rows
        ]

    return paginate(
        session,
        service.get_categories_query(type=type),
        transformer=transform,
    )
