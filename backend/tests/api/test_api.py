from unittest.mock import patch

from models import Episode


class TestEpisodes:
    def test_get_episodes_empty(self, client):
        response = client.get("/api/episodes")
        assert response.status_code == 200
        assert response.json()["items"] == []

    def test_get_episodes(self, client, db_session):
        episode = Episode(id=1, title="Test Episode")
        db_session.add(episode)
        db_session.commit()

        response = client.get("/api/episodes")
        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["items"][0]["title"] == "Test Episode"


class TestSimilarEpisodes:
    def test_get_similar_episodes_returns_results(self, client):
        similar = [
            Episode(id=2, title="Similar 1", slug="similar-1"),
            Episode(id=3, title="Similar 2", slug="similar-2"),
        ]
        with patch(
            "services.EpisodesService.get_similar_episodes",
            return_value=similar,
        ):
            response = client.get("/api/episodes/1/similar")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["title"] == "Similar 1"
        assert data[1]["title"] == "Similar 2"

    def test_get_similar_episodes_returns_empty_list(self, client):
        with patch(
            "services.EpisodesService.get_similar_episodes",
            return_value=[],
        ):
            response = client.get("/api/episodes/1/similar")

        assert response.status_code == 200
        assert response.json() == []

    def test_get_similar_episodes_default_limit(self, client):
        with patch(
            "services.EpisodesService.get_similar_episodes",
            return_value=[],
        ) as mock:
            client.get("/api/episodes/1/similar")

        mock.assert_called_once_with(1, 3)

    def test_get_similar_episodes_custom_limit(self, client):
        with patch(
            "services.EpisodesService.get_similar_episodes",
            return_value=[],
        ) as mock:
            client.get("/api/episodes/1/similar?limit=10")

        mock.assert_called_once_with(1, 10)

    def test_get_similar_episodes_limit_validation(self, client):
        response = client.get("/api/episodes/1/similar?limit=0")
        assert response.status_code == 422

        response = client.get("/api/episodes/1/similar?limit=21")
        assert response.status_code == 422
