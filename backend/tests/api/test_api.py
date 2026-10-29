from unittest.mock import patch

from models import Category, CategoryType, Episode, WikipediaArticle


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
        assert "wikipedia_articles" not in response.json()["items"][0]

    def test_get_episodes_search_length_validation(self, client):
        response = client.get("/api/episodes", params={"search": "a" * 100})
        assert response.status_code == 200

        response = client.get("/api/episodes", params={"search": "a" * 101})
        assert response.status_code == 422

    def test_get_episode_with_its_wikipedia_articles(self, client, db_session):
        url = "https://ca.wikipedia.org/wiki/Sardana"
        episode = Episode(
            id=1,
            title="La sardana",
            wikipedia_articles=[
                WikipediaArticle(title="Sardana", url=url),
                WikipediaArticle(title="Cobla", url="https://cobla"),
            ],
        )
        db_session.add(episode)
        db_session.commit()

        response = client.get("/api/episodes/1")

        assert response.status_code == 200
        assert response.json()["wikipedia_articles"] == [
            {"title": "Cobla", "url": "https://cobla"},
            {"title": "Sardana", "url": url},
        ]


class TestLocations:
    def test_get_locations(self, client, db_session):
        montserrat = Category(
            name="Montserrat",
            slug="montserrat",
            type=CategoryType.LOCATION,
            latitude=41.6,
            longitude=1.8,
        )
        db_session.add(
            Episode(id=1, title="La moreneta", categories=[montserrat])
        )
        db_session.commit()

        response = client.get("/api/locations")

        assert response.status_code == 200
        assert response.json() == [
            {
                "id": montserrat.id,
                "slug": "montserrat",
                "name": "Montserrat",
                "latitude": 41.6,
                "longitude": 1.8,
                "count": 1,
            }
        ]

    def test_get_category_counts(self, client, db_session):
        montserrat = Category(
            name="Montserrat",
            slug="montserrat",
            type=CategoryType.LOCATION,
        )
        guerra = Category(
            name="Guerra", slug="guerra", type=CategoryType.TOPIC
        )
        db_session.add_all(
            [
                Episode(id=1, title="La moreneta", categories=[montserrat]),
                Episode(
                    id=2, title="El Bruc", categories=[montserrat, guerra]
                ),
            ]
        )
        db_session.commit()

        response = client.get(
            "/api/categories/counts", params={"categories": "guerra"}
        )

        assert response.status_code == 200
        assert sorted(response.json(), key=lambda c: c["slug"]) == [
            {"slug": "guerra", "count": 1},
            {"slug": "montserrat", "count": 1},
        ]

    def test_get_episodes_match_all(self, client, db_session):
        guerra = Category(
            name="Guerra", slug="guerra", type=CategoryType.TOPIC
        )
        exili = Category(name="Exili", slug="exili", type=CategoryType.TOPIC)
        db_session.add_all(
            [
                Episode(id=1, title="Retirada", categories=[guerra, exili]),
                Episode(id=2, title="L'Ebre", categories=[guerra]),
            ]
        )
        db_session.commit()

        def titles(**params) -> list[str]:
            response = client.get(
                "/api/episodes",
                params={"categories": "guerra,exili", **params},
            )
            assert response.status_code == 200
            return sorted(e["title"] for e in response.json()["items"])

        assert titles() == ["L'Ebre", "Retirada"]
        assert titles(match_all="topic") == ["Retirada"]
        # Unknown types are left out.
        assert titles(match_all="tema") == ["L'Ebre", "Retirada"]

    def test_get_location_stats(self, client, db_session):
        montserrat = Category(
            name="Montserrat",
            slug="montserrat",
            type=CategoryType.LOCATION,
            latitude=41.6,
            longitude=1.8,
        )
        db_session.add_all(
            [
                Episode(id=1, title="La moreneta", categories=[montserrat]),
                Episode(id=2, title="Sense lloc"),
            ]
        )
        db_session.commit()

        response = client.get("/api/locations/stats")

        assert response.status_code == 200
        assert response.json() == {"episodes": 1, "total": 2}


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
        # The cards only show these, so nothing else is sent.
        assert set(data[0]) == {
            "id",
            "title",
            "slug",
            "published_at",
            "image_url",
        }

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
