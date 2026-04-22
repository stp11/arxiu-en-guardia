from unittest.mock import MagicMock

from repositories import IEpisodesRepository
from services import EpisodesService


class TestEpisodesService:
    def setup_method(self):
        self.mock_repo = MagicMock(spec=IEpisodesRepository)
        self.service = EpisodesService(episodes_repository=self.mock_repo)

    def test_episodes_service_calls_repository(self):
        search_term = "test"
        order_direction = "desc"

        self.service.get_episodes_query(
            search=search_term, order=order_direction
        )

        self.mock_repo.get_episodes_query.assert_called_once_with(
            search=search_term, order=order_direction, categories=[]
        )

    def test_episodes_service_calls_repository_with_categories(self):
        result = self.service._parse_categories(
            categories_str="guerra-civil, roma-antiga ,edat-mitjana"
        )
        assert result == ["guerra-civil", "roma-antiga", "edat-mitjana"]

    def test_episodes_service_get_episode_by_id(self):
        self.service.get_episode_by_id(id=1)
        self.mock_repo.get_episode_by_id.assert_called_once_with(1)

    def test_extract_image_url_prefers_wcr_audio(self):
        data = {
            "imatges": {
                "imatge": [
                    {
                        "text": "https://example.com/program.jpg",
                        "mida": "670x378",
                        "tipologia": "WCR_PROGRAMA",
                    },
                    {
                        "text": "https://example.com/audio.jpg",
                        "mida": "670x378",
                        "tipologia": "WCR_AUDIO",
                    },
                ]
            }
        }
        assert (
            self.service._extract_image_url(data)
            == "https://example.com/audio.jpg"
        )

    def test_extract_image_url_falls_back_to_first_candidate(self):
        data = {
            "imatges": {
                "imatge": [
                    {
                        "text": "https://example.com/program.jpg",
                        "mida": "670x378",
                        "tipologia": "WCR_PROGRAMA",
                    },
                ]
            }
        }
        assert (
            self.service._extract_image_url(data)
            == "https://example.com/program.jpg"
        )

    def test_extract_image_url_returns_none_when_no_images(self):
        assert self.service._extract_image_url({}) is None

    def test_extract_image_url_ignores_other_sizes(self):
        data = {
            "imatges": {
                "imatge": [
                    {
                        "text": "https://example.com/small.jpg",
                        "mida": "100x100",
                        "tipologia": "WCR_AUDIO",
                    },
                ]
            }
        }
        assert self.service._extract_image_url(data) is None
