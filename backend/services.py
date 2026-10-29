import json
from datetime import datetime, timezone

from openai import OpenAI
from sqlalchemy import Select

from logger import logger
from models import (
    Category,
    CategoryCount,
    CategoryType,
    Episode,
    LocationStats,
    LocationWithCount,
)
from prompts import (  # noqa: E501
    CLASSIFICATION_KEYS,
    CLASSIFICATION_SCHEMA,
    WIKIPEDIA_ARTICLES_SCHEMA,
    WIKIPEDIA_CHOICES_SCHEMA,
    classification_prompt,
    wikipedia_articles_prompt,
    wikipedia_choices_prompt,
)
from repositories import (
    ICategoriesRepository,
    IEpisodesRepository,
    IWikipediaArticlesRepository,
)
from wikipedia import Article, WikipediaClient

CATEGORY_TYPE_TO_KEY: dict[CategoryType, str] = {
    CategoryType.TOPIC: "temàtica",
    CategoryType.TIME_PERIOD: "època",
    CategoryType.CHARACTER: "personatges",
    CategoryType.LOCATION: "localització",
}


def parse_categories(categories_str: str) -> list[str]:
    """
    Parse comma-separated category slugs string into a list.
    """
    if not categories_str or not categories_str.strip():
        return []

    return [cat.strip() for cat in categories_str.split(",") if cat.strip()]


def parse_match_all(match_all_str: str) -> set[CategoryType]:
    """
    Parse comma-separated category types, already checked by the API.
    """
    return {CategoryType(t) for t in parse_categories(match_all_str)}


class EpisodesService:
    def __init__(self, episodes_repository: IEpisodesRepository):
        self.episodes_repository = episodes_repository

    def get_episodes_query(
        self,
        search: str | None,
        order: str,
        categories: str = "",
        match_all: str = "",
    ) -> Select:
        """
        Orchestrates fetching the episodes query from the repository.
        """
        return self.episodes_repository.get_episodes_query(
            search=search,
            order=order,
            categories=parse_categories(categories),
            match_all=parse_match_all(match_all),
        )

    def get_episode_by_id(self, id: int) -> Episode:
        return self.episodes_repository.get_episode_by_id(id)

    def get_similar_episodes(
        self, id: int, limit: int
    ) -> list[Episode] | None:
        """None if there's no such episode, empty if it has no embedding."""
        episode = self.episodes_repository.get_episode_by_id(id)
        if episode is None:
            return None
        if episode.embedding is None:
            return []
        return self.episodes_repository.get_similar_episodes(episode, limit)

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
            model="gpt-6-luna",
            messages=[{"role": "user", "content": prompt}],
            # Luna defaults to "medium", which rejects temperature
            reasoning_effort="none",
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

    def get_category_counts(
        self, search: str | None, categories: str = "", match_all: str = ""
    ) -> list[CategoryCount]:
        return self.categories_repository.get_category_counts(
            search=search,
            categories=parse_categories(categories),
            match_all=parse_match_all(match_all),
        )

    def get_locations(self) -> list[LocationWithCount]:
        return self.categories_repository.get_locations()

    def get_location_stats(self) -> LocationStats:
        return self.categories_repository.get_location_stats()


class GeocodingService:
    def __init__(self, wikipedia_client: WikipediaClient):
        self.wikipedia_client = wikipedia_client

    def geocode(self, locations: list[Category]) -> list[Category]:
        """
        Places each location where its Catalan Wikipedia article says, and
        returns those it couldn't: without an article, at a disambiguation
        page, or at an article without coordinates. Those keep whatever
        coordinates they had; all count as looked up.
        """
        found = self.wikipedia_client.lookup(
            location.name for location in locations
        )
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        unplaced = []
        for location in locations:
            article = found[location.name]
            if article and article.coordinates and not article.disambiguation:
                location.latitude, location.longitude = article.coordinates
            else:
                unplaced.append(location)
            location.geocoded_at = now
        return unplaced


class WikipediaLinkingService:
    MODEL = "gpt-6-luna"
    MAX_ARTICLES = 3
    SEARCH_RESULTS = 5

    def __init__(
        self,
        openai_client: OpenAI,
        wikipedia_client: WikipediaClient,
        episodes_repository: IEpisodesRepository,
        articles_repository: IWikipediaArticlesRepository,
    ):
        self.openai_client = openai_client
        self.wikipedia_client = wikipedia_client
        self.episodes_repository = episodes_repository
        self.articles_repository = articles_repository

    def find_articles(self, episode: Episode) -> list[Article]:
        """
        The Wikipedia articles about the episode, most important first. The
        model proposes titles from what it knows, and Wikipedia confirms
        them; a title with no article, or a disambiguation page, is
        searched for and the model picks among the results.
        """
        names = self._propose_names(episode)
        found = self.wikipedia_client.lookup(names)
        articles = {
            name: article
            for name, article in found.items()
            if article and not article.disambiguation
        }
        unresolved = [name for name in names if name not in articles]
        if unresolved:
            articles.update(self._choose_from_search(episode, unresolved))

        # Different names can lead to the same article.
        unique = {}
        for name in names:
            if name in articles:
                unique.setdefault(articles[name].title, articles[name])
        return list(unique.values())

    def save_articles(self, episode: Episode, articles: list[Article]) -> None:
        for article in articles:
            saved = self.articles_repository.get_or_create_article(
                article.title, article.url
            )
            self.episodes_repository.link_episode_to_article(
                episode.id, saved.id
            )
        episode.wikipedia_checked_at = datetime.now(timezone.utc).replace(
            tzinfo=None
        )
        logger.info(
            f"Linked episode {episode.id} to Wikipedia articles "
            f"{[article.title for article in articles]}"
        )

    def _propose_names(self, episode: Episode) -> list[str]:
        prompt = wikipedia_articles_prompt(
            episode,
            self.MAX_ARTICLES,
            [category.name for category in episode.categories],
        )
        result = self._complete(prompt, WIKIPEDIA_ARTICLES_SCHEMA)
        names = [name.strip() for name in result["articles"] if name.strip()]
        return list(dict.fromkeys(names))[: self.MAX_ARTICLES]

    def _choose_from_search(
        self, episode: Episode, names: list[str]
    ) -> dict[str, Article]:
        searches = {}
        for id, name in enumerate(names, start=1):
            results = [
                article
                for article in self.wikipedia_client.search(
                    name, limit=self.SEARCH_RESULTS
                )
                if not article.disambiguation
            ]
            if results:
                searches[id] = (name, results)
        if not searches:
            return {}

        prompt = wikipedia_choices_prompt(episode, searches)
        result = self._complete(prompt, WIKIPEDIA_CHOICES_SCHEMA)
        chosen = {}
        for choice in result["choices"]:
            if choice["id"] not in searches:
                continue
            name, results = searches[choice["id"]]
            # Only a title among the results is known to exist.
            by_title = {article.title: article for article in results}
            if choice["title"] in by_title:
                chosen[name] = by_title[choice["title"]]
        return chosen

    def _complete(self, prompt: str, schema: dict) -> dict:
        response = self.openai_client.chat.completions.create(
            model=self.MODEL,
            messages=[{"role": "user", "content": prompt}],
            # Luna defaults to "medium", which rejects temperature
            reasoning_effort="none",
            temperature=0,
            response_format={"type": "json_schema", "json_schema": schema},
        )
        return json.loads(response.choices[0].message.content)
