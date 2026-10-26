import re
from datetime import datetime
from unittest.mock import Mock

from sqlmodel import select

from commands.ingest_data import ingest_data
from models import Episode, IngestionPosition


def mock_api_response(items, pagination=None):
    class MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "resposta": {"items": {"item": items}, "paginacio": pagination}
            }

    return lambda *args, **kwargs: MockResponse()


def create_paginated_mock(paginated_data: dict):
    total_pages = len(paginated_data)

    def mock_paginated_response(url, timeout):
        match = re.search(r"pagina=(\d+)", url)
        page = int(match.group(1)) if match else 1

        items_for_page = paginated_data.get(page, [])
        pagination_info = {"total_pagines": total_pages}

        return mock_api_response(items_for_page, pagination_info)()

    return mock_paginated_response


class TestIngestData:
    def setup_method(self):
        self.items = [
            {
                "id": 1,
                "titol": "Test Episode",
                "nom_friendly": "test-episode",
                "entradeta": "A test episode",
                "data_publicacio": "01/01/2020 00:00:00",
            },
            {
                "id": 2,
                "titol": "Test Episode 2",
                "nom_friendly": "test-episode-2",
                "entradeta": "A test episode 2",
                "data_publicacio": "01/01/2020 00:00:00",
            },
            {
                "id": 3,
                "titol": "Test Episode 3",
                "nom_friendly": "test-episode-3",
                "entradeta": "A test episode 3",
                "data_publicacio": "01/01/2020 00:00:00",
            },
        ]
        self.pagination = {
            "total_pagines": 3,
            "pagina_actual": 1,
            "items_pagina": 3,
        }

    def test_ingest_all_episodes(self, db_session, monkeypatch):
        monkeypatch.setattr(
            "commands.ingest_data.requests.get",
            mock_api_response(self.items, self.pagination),
        )
        monkeypatch.setattr(
            "commands.ingest_data.get_session", lambda: iter([db_session])
        )

        ingest_data()
        episodes = db_session.exec(select(Episode)).all()
        assert len(episodes) == 3

    def test_no_new_data_to_ingest(self, db_session, monkeypatch):
        monkeypatch.setattr(
            "commands.ingest_data.requests.get",
            mock_api_response(self.items, self.pagination),
        )
        monkeypatch.setattr(
            "commands.ingest_data.get_session", lambda: iter([db_session])
        )

        # Add existing episodes to the database before ingestion
        for item in self.items:
            episode = Episode(id=item["id"], title=item["titol"])
            db_session.add(episode)

        db_session.commit()

        ingest_data()
        episodes = db_session.exec(select(Episode)).all()

        # No new episodes should be ingested
        assert len(episodes) == 3
        assert {e.id for e in episodes} == {item["id"] for item in self.items}

    def test_reingesting_keeps_what_was_worked_out_here(
        self, db_session, monkeypatch
    ):
        monkeypatch.setattr(
            "commands.ingest_data.requests.get",
            mock_api_response(self.items[:1], {"total_pagines": 1}),
        )
        monkeypatch.setattr(
            "commands.ingest_data.get_session", lambda: iter([db_session])
        )
        checked_at = datetime(2026, 10, 1)
        db_session.add(
            Episode(
                id=1,
                title="Old title",
                embedding=[0.0] * 1536,
                wikipedia_checked_at=checked_at,
            )
        )
        db_session.commit()

        ingest_data()
        db_session.expire_all()
        episode = db_session.get(Episode, 1)

        assert episode.title == "Test Episode"
        assert episode.wikipedia_checked_at == checked_at
        assert episode.embedding is not None

    def test_ingest_paginated_data(self, db_session, monkeypatch):
        """
        Tests that ingestion continues over multiple pages.
        """
        mock_function = create_paginated_mock(
            {1: self.items[0:1], 2: self.items[1:2], 3: self.items[2:3]}
        )

        mock_get = Mock(side_effect=mock_function)

        monkeypatch.setattr("commands.ingest_data.requests.get", mock_get)
        monkeypatch.setattr(
            "commands.ingest_data.get_session", lambda: iter([db_session])
        )

        ingest_data()

        episodes = db_session.exec(select(Episode)).all()
        assert mock_get.call_count == 3
        assert len(episodes) == 3

    def test_ingest_incremental_update(self, db_session, monkeypatch):
        """
        Tests that ingestion stops when it finds an already existing episode.
        """
        position = IngestionPosition(id=1, last_episode_id=2)
        db_session.add(position)
        db_session.commit()

        mock_api_items = [
            {
                "id": 3,
                "titol": "New Episode 3",
                "data_publicacio": "03/01/2020 00:00:00",
            },
            {
                "id": 2,
                "titol": "Existing Episode 2",
                "data_publicacio": "02/01/2020 00:00:00",
            },
            {
                "id": 1,
                "titol": "Old Episode 1",
                "data_publicacio": "01/01/2020 00:00:00",
            },
        ]
        monkeypatch.setattr(
            "commands.ingest_data.requests.get",
            mock_api_response(mock_api_items, self.pagination),
        )
        monkeypatch.setattr(
            "commands.ingest_data.get_session", lambda: iter([db_session])
        )

        ingest_data()

        # only one new episode (ID=3) should have been added.
        episodes = db_session.exec(select(Episode)).all()
        assert len(episodes) == 1
        assert episodes[0].id == 3

        # IngestionPosition should be updated to the newest ID
        updated_position = db_session.get(IngestionPosition, 1)
        assert updated_position.last_episode_id == 3
