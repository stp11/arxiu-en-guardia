import json
import re
from datetime import datetime
from types import SimpleNamespace

from sqlmodel import select

from commands.link_wikipedia_articles import link_wikipedia_articles
from models import Episode, EpisodeWikipediaArticle, WikipediaArticle
from wikipedia import Article


class FakeOpenAI:
    """Proposes article names for each episode title."""

    def __init__(self, names: dict[str, list[str] | Exception]):
        self.names = names
        self.titles = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._complete)
        )

    def _complete(self, messages, **kwargs):
        prompt = messages[0]["content"]
        title = re.search(r"## TÍTOL\n(.+)\n", prompt).group(1)
        self.titles.append(title)
        names = self.names[title]
        if isinstance(names, Exception):
            raise names
        content = json.dumps({"articles": names})
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


class FakeWikipedia:
    ARTICLES = ["Sardana", "Mahoma", "Cobla"]

    def lookup(self, titles):
        return {
            title: (
                Article(title, f"https://ca.wikipedia.org/wiki/{title}")
                if title in self.ARTICLES
                else None
            )
            for title in titles
        }

    def search(self, text, limit):
        return []


class TestLinkWikipediaArticles:
    def seed(self, db_session):
        manual = WikipediaArticle(title="Cobla", url="https://cobla")
        db_session.add_all(
            [
                Episode(id=1, title="La sardana", published_at=at(5)),
                Episode(id=2, title="Vida de Mahoma", published_at=at(4)),
                Episode(id=3, title="Sense article", published_at=at(3)),
                Episode(
                    id=4,
                    title="Ja revisat",
                    published_at=at(2),
                    wikipedia_checked_at=at(6),
                ),
                Episode(
                    id=5,
                    title="Enllaçat a mà",
                    published_at=at(1),
                    wikipedia_articles=[manual],
                ),
            ]
        )
        db_session.commit()

    def run(self, db_session, monkeypatch, names, **kwargs) -> list[str]:
        fake = FakeOpenAI(names)
        monkeypatch.setattr(
            "commands.link_wikipedia_articles.OpenAI", lambda api_key: fake
        )
        monkeypatch.setattr(
            "commands.link_wikipedia_articles.WikipediaClient", FakeWikipedia
        )
        monkeypatch.setattr(
            "commands.link_wikipedia_articles.get_session",
            lambda: iter([db_session]),
        )

        link_wikipedia_articles(**kwargs)

        db_session.expire_all()
        return fake.titles

    def titles(self, db_session, episode_id: int) -> list[str]:
        episode = db_session.get(Episode, episode_id)
        return [article.title for article in episode.wikipedia_articles]

    def test_links_only_episodes_not_checked_or_linked_yet(
        self, db_session, monkeypatch
    ):
        self.seed(db_session)

        prompted = self.run(
            db_session,
            monkeypatch,
            {
                "La sardana": ["Sardana", "Cobla", "Sardanes de lluny"],
                "Vida de Mahoma": ["Mahoma"],
                "Sense article": [],
            },
        )

        assert prompted == ["La sardana", "Vida de Mahoma", "Sense article"]
        assert self.titles(db_session, 1) == ["Cobla", "Sardana"]
        assert self.titles(db_session, 2) == ["Mahoma"]
        assert self.titles(db_session, 3) == []
        for id in (1, 2, 3):
            assert db_session.get(Episode, id).wikipedia_checked_at
        assert db_session.get(Episode, 4).wikipedia_checked_at == at(6)
        assert db_session.get(Episode, 5).wikipedia_checked_at is None
        # The admin's "Cobla" is reused, not duplicated.
        articles = db_session.exec(select(WikipediaArticle)).all()
        assert sorted(a.title for a in articles) == [
            "Cobla",
            "Mahoma",
            "Sardana",
        ]

    def test_processes_the_newest_episodes_first(
        self, db_session, monkeypatch
    ):
        self.seed(db_session)

        prompted = self.run(
            db_session,
            monkeypatch,
            {"La sardana": ["Sardana"]},
            max_total=1,
        )

        assert prompted == ["La sardana"]
        assert db_session.get(Episode, 2).wikipedia_checked_at is None

    def test_leaves_failed_episodes_for_the_next_run(
        self, db_session, monkeypatch
    ):
        self.seed(db_session)

        prompted = self.run(
            db_session,
            monkeypatch,
            {
                "La sardana": RuntimeError("OpenAI is down"),
                "Vida de Mahoma": ["Mahoma"],
                "Sense article": [],
            },
            batch_size=1,
        )

        assert prompted == ["La sardana", "Vida de Mahoma", "Sense article"]
        assert db_session.get(Episode, 1).wikipedia_checked_at is None
        assert self.titles(db_session, 2) == ["Mahoma"]

    def test_dry_run_saves_nothing(self, db_session, monkeypatch):
        self.seed(db_session)

        prompted = self.run(
            db_session,
            monkeypatch,
            {
                "La sardana": ["Sardana"],
                "Vida de Mahoma": ["Mahoma"],
                "Sense article": [],
            },
            batch_size=1,
            dry_run=True,
        )

        assert prompted == ["La sardana", "Vida de Mahoma", "Sense article"]
        links = db_session.exec(select(EpisodeWikipediaArticle)).all()
        assert [link.episode_id for link in links] == [5]
        assert len(db_session.exec(select(WikipediaArticle)).all()) == 1
        checked = db_session.exec(
            select(Episode).where(Episode.wikipedia_checked_at.isnot(None))
        ).all()
        assert [episode.id for episode in checked] == [4]


def at(day: int) -> datetime:
    return datetime(2026, 10, day, 17, 0)
