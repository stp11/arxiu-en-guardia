from types import SimpleNamespace

from commands.backfill_embeddings import (
    _episode_embedding_text,
    backfill_embeddings,
)
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

    def test_embeds_episodes_without_a_description(
        self, db_session, monkeypatch
    ):
        db_session.add(Episode(id=4, title="Casp"))
        db_session.commit()

        embedded = self.run(db_session, monkeypatch)

        assert embedded == ["Casp"]

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

    def test_refresh_re_embeds_only_the_episodes_asked_for(
        self, db_session, monkeypatch
    ):
        self.seed(db_session)

        embedded = self.run(
            db_session,
            monkeypatch,
            batch_size=1,
            refresh=True,
            episode_ids=[1, 3],
        )

        assert sorted(embedded) == ["Almansa | 1707", "Olivares | 1640"]
        assert list(db_session.get(Episode, 1).embedding) == NEW
        assert list(db_session.get(Episode, 2).embedding) == OLD


class TestEpisodeEmbeddingText:
    def test_drops_the_episode_and_chapter_numbers(self):
        episode = Episode(
            title="702 - Els anglesos a la guerra del Francès",
            description="Capítol 1.000 - Tercera part. La flota anglesa.",
        )

        assert _episode_embedding_text(episode) == (
            "Els anglesos a la guerra del Francès | La flota anglesa."
        )

    def test_drops_the_placeholder_description(self):
        episode = Episode(
            title="153 - L'aigua i els romans", description="En guàrdia"
        )

        assert _episode_embedding_text(episode) == "L'aigua i els romans"

    def test_drops_the_guests_but_not_their_books(self):
        episode = Episode(
            title="Les companyies mercenàries",
            description=(
                "Capítol 1299. Entraven, saquejaven i es feien fonedissos. "
                "En parlem amb Josep Maria Solé i Sabaté, historiador, i "
                "Flocel Sabaté, catedràtic d'Història Medieval de la UdL. "
                'També és autor del llibre "Companyies estranyes d\'armes".'
            ),
        )

        assert _episode_embedding_text(episode) == (
            "Les companyies mercenàries | Entraven, saquejaven i es feien "
            "fonedissos. Companyies estranyes d'armes"
        )

    def test_drops_html(self):
        episode = Episode(
            title="La revolta hongaresa",
            description="L&#x2019;<b>Exèrcit Roig</b> la va aplacar.",
        )

        assert _episode_embedding_text(episode) == (
            "La revolta hongaresa | L’Exèrcit Roig la va aplacar."
        )
