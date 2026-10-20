from types import SimpleNamespace

from commands.backfill_embeddings import backfill_embeddings
from models import Episode

OLD = [0.0] * 1536
NEW = [1.0] * 1536


class FakeOpenAI:
    def __init__(self):
        self.embedded = []
        self.embeddings = SimpleNamespace(create=self._embed)

    def _embed(self, input, model):
        self.embedded += input
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=NEW) for _ in input]
        )


class TestBackfillEmbeddings:
    def seed(self, db_session):
        db_session.add_all(
            [
                Episode(
                    id=1, title="Almansa", description="1707", embedding=OLD
                ),
                Episode(
                    id=2, title="Montsó", description="Corts", embedding=OLD
                ),
                Episode(id=3, title="Olivares", description="1640"),
            ]
        )
        db_session.commit()

    def run(self, db_session, monkeypatch, **kwargs) -> list[str]:
        fake = FakeOpenAI()
        monkeypatch.setattr(
            "commands.backfill_embeddings.OpenAI", lambda api_key: fake
        )
        monkeypatch.setattr(
            "commands.backfill_embeddings.get_session",
            lambda: iter([db_session]),
        )

        backfill_embeddings(**kwargs)

        return fake.embedded

    def test_embeds_only_episodes_without_one(self, db_session, monkeypatch):
        self.seed(db_session)

        embedded = self.run(db_session, monkeypatch)

        assert embedded == ["Olivares | 1640"]
        assert list(db_session.get(Episode, 1).embedding) == OLD

    def test_refresh_re_embeds_every_episode_once(
        self, db_session, monkeypatch
    ):
        self.seed(db_session)

        embedded = self.run(
            db_session, monkeypatch, batch_size=2, refresh=True
        )

        assert sorted(embedded) == [
            "Almansa | 1707",
            "Montsó | Corts",
            "Olivares | 1640",
        ]
        for id in (1, 2, 3):
            assert list(db_session.get(Episode, id).embedding) == NEW
