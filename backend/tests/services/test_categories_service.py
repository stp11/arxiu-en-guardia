import json
from unittest.mock import MagicMock

from openai import OpenAI

from models import Category, CategoryType, Episode
from repositories import ICategoriesRepository, IEpisodesRepository
from services import CategoriesService, ClassificationService


class TestClassificationService:
    def setup_method(self):
        self.mock_openai_client = MagicMock(spec=OpenAI)
        self.mock_episodes_repo = MagicMock(spec=IEpisodesRepository)
        self.mock_categories_repo = MagicMock(spec=ICategoriesRepository)

        self.service = ClassificationService(
            openai_client=self.mock_openai_client,
            episodes_repository=self.mock_episodes_repo,
            categories_repository=self.mock_categories_repo,
        )

    def test_classify_episode_successful_classification(self):
        episode = Episode(
            id=1,
            title="Test Episode",
            description="Conquesta de Mallorca per Jaume I",
        )

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(
            {
                "temàtica": ["temàtica 1", "temàtica 2"],
                "personatges": ["Jaume I"],
                "localització": ["Mallorca"],
                "època": ["medieval"],
            }
        )
        self.mock_openai_client.chat.completions.create.return_value = (
            mock_response
        )

        result = self.service.classify_episode(episode)

        assert isinstance(result, dict)
        assert result["temàtica"] == ["temàtica 1", "temàtica 2"]
        assert result["personatges"] == ["Jaume I"]
        assert result["època"] == ["medieval"]
        assert result["localització"] == ["Mallorca"]

        self.mock_openai_client.chat.completions.create.assert_called_once()
        create = self.mock_openai_client.chat.completions.create
        assert create.call_args.kwargs["model"] == "gpt-6-luna"
        assert create.call_args.kwargs["reasoning_effort"] == "none"

    def test_classify_episode_json_decode_error_returns_none(self):
        episode = Episode(
            id=1,
            title="Test Episode",
            description="Conquesta de Mallorca per Jaume I",
        )

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Invalid JSON response"
        self.mock_openai_client.chat.completions.create.return_value = (
            mock_response
        )

        result = self.service.classify_episode(episode)
        assert result is None

    def test_save_categories_to_episode_with_dict_classification(self):
        episode = Episode(
            id=1, title="Conquesta de Mallorca i València per Jaume I"
        )
        classification = {
            "temàtica": ["Conquesta de Mallorca i València"],
            "personatges": ["Jaume I"],
            "època": ["medieval"],
            "localització": ["Mallorca", "València"],
        }

        mock_categories = [
            Category(
                id=1,
                slug="Conquesta de Mallorca i València",
                name="Conquesta de Mallorca i València",
            ),
            Category(id=1, slug="Jaume I", name="Jaume I"),
            Category(id=2, slug="medieval", name="medieval"),
            Category(id=3, slug="Mallorca", name="Mallorca"),
            Category(id=4, slug="València", name="València"),
        ]
        self.mock_categories_repo.get_or_create_category.side_effect = (
            mock_categories
        )

        self.service.save_categories_to_episode(episode, classification)

        assert self.mock_categories_repo.get_or_create_category.call_count == 5
        assert self.mock_episodes_repo.link_episode_to_category.call_count == 5
        for i, category in enumerate(mock_categories):
            self.mock_episodes_repo.link_episode_to_category.assert_any_call(
                1, category.id
            )

    def test_save_categories_to_episode_empty_classification(self):
        episode = Episode(id=1, title="Test Episode")
        classification = {}

        self.service.save_categories_to_episode(episode, classification)
        self.mock_categories_repo.get_or_create_category.assert_not_called()
        self.mock_episodes_repo.link_episode_to_category.assert_not_called()


class TestCategoriesService:
    def setup_method(self):
        self.mock_categories_repo = MagicMock(spec=ICategoriesRepository)
        self.service = CategoriesService(
            categories_repository=self.mock_categories_repo
        )

    def test_get_categories(self):
        self.service.get_categories(CategoryType.TOPIC)
        self.mock_categories_repo.get_categories.assert_called_once_with(
            type=CategoryType.TOPIC
        )

    def test_get_category_counts(self):
        self.service.get_category_counts(
            "atenes", "guerra, catalunya", "topic, location"
        )
        self.mock_categories_repo.get_category_counts.assert_called_once_with(
            search="atenes",
            categories=["guerra", "catalunya"],
            match_all={CategoryType.TOPIC, CategoryType.LOCATION},
        )
