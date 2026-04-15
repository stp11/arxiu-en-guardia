import json
from datetime import datetime

from openai import OpenAI
from sqlalchemy import Select

from logger import logger
from models import Category, CategoryType, Episode
from prompts import (  # noqa: E501
    CLASSIFICATION_KEYS,
    CLASSIFICATION_SCHEMA,
    classification_prompt,
)
from repositories import ICategoriesRepository, IEpisodesRepository

CATEGORY_TYPE_TO_KEY: dict[CategoryType, str] = {
    CategoryType.TOPIC: "temàtica",
    CategoryType.TIME_PERIOD: "època",
    CategoryType.CHARACTER: "personatges",
    CategoryType.LOCATION: "localització",
}


class EpisodesService:
    def __init__(self, episodes_repository: IEpisodesRepository):
        self.episodes_repository = episodes_repository

    def get_episodes_query(
        self, search: str | None, order: str, categories: str = ""
    ) -> Select:
        """
        Orchestrates fetching the episodes query from the repository.
        """
        category_list = self._parse_categories(categories)

        return self.episodes_repository.get_episodes_query(
            search=search, order=order, categories=category_list
        )

    def get_episode_by_id(self, id: int) -> Episode:
        return self.episodes_repository.get_episode_by_id(id)

    def _parse_categories(self, categories_str: str) -> list[int]:
        """
        Parse comma-separated category IDs string into a list of integers.
        """
        category_list = []

        if not categories_str or not categories_str.strip():
            return category_list

        try:
            category_list = [
                int(cat.strip())
                for cat in categories_str.split(",")
                if cat.strip()
            ]
        except ValueError as e:
            logger.warning(
                f"Failed to parse categories '{categories_str}': {e}"
            )
            category_list = []

        return category_list

    def create_episode_from_api_data(self, data: dict) -> Episode:
        """Maps API data dictionary to an Episode object."""
        return Episode(
            id=data["id"],
            title=data.get("titol"),
            slug=data.get("nom_friendly"),
            description=data.get("entradeta"),
            published_at=(
                self._parse_date(data["data_publicacio"])
                if data.get("data_publicacio")
                else None
            ),
            image_url=self._extract_image_url(data),
        )

    @staticmethod
    def _extract_image_url(data: dict) -> str | None:
        """Extract the 670x378 image URL from API data.

        Prefers episode-specific images (WCR_AUDIO) over program-level ones.
        """
        images = data.get("imatges", {}).get("imatge", [])
        candidates = [img for img in images if img.get("mida") == "670x378"]

        for img in candidates:
            if img.get("tipologia") == "WCR_AUDIO":
                return img.get("text")

        return candidates[0].get("text") if candidates else None

    def _parse_date(self, date_str: str) -> datetime:
        """Parse API date format: '09/09/2001 00:01:00'"""
        return datetime.strptime(date_str, "%d/%m/%Y %H:%M:%S")


class ClassificationService:
    def __init__(
        self,
        openai_client: OpenAI,
        episodes_repository: IEpisodesRepository,
        categories_repository: ICategoriesRepository,
    ):
        self.openai_client = openai_client
        self.episodes_repository = episodes_repository
        self.categories_repository = categories_repository

    def classify_episode(self, episode: Episode) -> dict | None:
        """Classify a single episode using OpenAI."""
        existing_categories = self.categories_repository.get_all_categories()
        grouped = self._group_categories_by_key(existing_categories)
        prompt = classification_prompt(episode, grouped)

        logger.info(f"Prompt: {prompt}")

        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={
                "type": "json_schema",
                "json_schema": CLASSIFICATION_SCHEMA,
            },
        )

        logger.info(f"Classification response: {response}")
        try:
            result = json.loads(response.choices[0].message.content)
            logger.info(f"Classification result: {result}")
            return result
        except Exception as e:
            logger.error(
                f"Failed to fetch classification from LLM for episode {episode.id}: {e}"  # noqa: E501
            )
            return None

    @staticmethod
    def _group_categories_by_key(
        categories: list[Category],
    ) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {
            key: [] for key in CLASSIFICATION_KEYS
        }
        for category in categories:
            key = CATEGORY_TYPE_TO_KEY.get(category.type)
            if key is None:
                continue
            grouped[key].append(category.name)
        return grouped

    def save_categories_to_episode(
        self, episode: Episode, classification: dict | None
    ) -> None:
        """Save classified categories to the database."""
        all_categories = []

        if classification is None:
            logger.info(f"No classification found for episode {episode.id}")
            return

        try:
            for category_type, category_names in classification.items():
                for name in category_names:
                    type = self.categories_repository.map_category_type(
                        category_type
                    )
                    category = (
                        self.categories_repository.get_or_create_category(
                            name, type
                        )
                    )
                    logger.info(f"Saved category: {category}")
                    all_categories.append(category)
        except Exception as e:
            logger.error(f"Failed to save categories: {e}")
            return

        for category in all_categories:
            logger.info(
                f"Linking episode {episode.id} to category {category.id}"
            )
            self.episodes_repository.link_episode_to_category(
                episode.id, category.id
            )
        logger.info(
            f"Linked episode {episode.id} to categories {all_categories}"
        )


class CategoriesService:
    def __init__(self, categories_repository: ICategoriesRepository):
        self.categories_repository = categories_repository

    def get_categories_query(self, type: CategoryType) -> Select:
        return self.categories_repository.get_categories_query(type=type)
