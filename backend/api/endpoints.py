from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi_pagination import Page
from fastapi_pagination.customization import CustomizedPage, UseParamsFields

from dependencies import get_categories_service, get_episodes_service
from models import (
    CategoryCount,
    CategoryType,
    CategoryWithCount,
    EpisodeDetail,
    EpisodeSummary,
    EpisodeWithCategories,
    LocationStats,
    LocationWithCount,
)
from services import CategoriesService, EpisodesService, parse_categories

router = APIRouter()


@dataclass
class EpisodeFilters:
    """The filters shared by the episode list and its facet counts."""

    search: str = Query("", max_length=100)
    categories: str = Query(
        "", description="Comma-separated list of category slugs"
    )
    match_all: str = Query(
        "",
        description=(
            "Comma-separated list of category types whose selected categories"
            " must all match, rather than any of them"
        ),
    )

    def __post_init__(self):
        types = {t.value for t in CategoryType}
        unknown = [
            t for t in parse_categories(self.match_all) if t not in types
        ]
        if unknown:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown category types: {', '.join(unknown)}",
            )


@router.get(
    "/episodes", tags=["episodis"], response_model=Page[EpisodeWithCategories]
)
def get_episodes(
    service: EpisodesService = Depends(get_episodes_service),
    filters: EpisodeFilters = Depends(),
    order: Literal["asc", "desc"] = "desc",
):
    return service.get_episodes(
        search=filters.search,
        order=order,
        categories=filters.categories,
        match_all=filters.match_all,
    )


@router.get("/episodes/{id}", tags=["episodis"], response_model=EpisodeDetail)
def get_episode(
    id: int = Path(..., description="Episode ID"),
    service: EpisodesService = Depends(get_episodes_service),
):
    episode = service.get_episode_by_id(id)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    return episode


@router.get(
    "/episodes/{id}/similar",
    tags=["episodis"],
    response_model=list[EpisodeSummary],
)
def get_similar_episodes(
    id: int = Path(..., description="Episode ID"),
    limit: int = Query(3, ge=1, le=20, description="Number of results"),
    service: EpisodesService = Depends(get_episodes_service),
):
    similar = service.get_similar_episodes(id, limit)
    if similar is None:
        raise HTTPException(status_code=404, detail="Episode not found")
    return similar


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
    type: CategoryType = Query(..., description="Category type"),
):
    return service.get_categories(type=type)


@router.get(
    "/categories/counts",
    tags=["categories"],
    response_model=list[CategoryCount],
)
def get_category_counts(
    service: CategoriesService = Depends(get_categories_service),
    filters: EpisodeFilters = Depends(),
):
    # Per category, its episodes under the filters of the other types, and
    # of its own if in match_all; those with none are left out.
    return service.get_category_counts(
        search=filters.search,
        categories=filters.categories,
        match_all=filters.match_all,
    )


@router.get(
    "/locations",
    tags=["localitzacions"],
    response_model=list[LocationWithCount],
)
def get_locations(
    service: CategoriesService = Depends(get_categories_service),
):
    # All of them: the map shows every place at once.
    return service.get_locations()


@router.get(
    "/locations/stats", tags=["localitzacions"], response_model=LocationStats
)
def get_location_stats(
    service: CategoriesService = Depends(get_categories_service),
):
    return service.get_location_stats()
