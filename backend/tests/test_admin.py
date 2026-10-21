import asyncio
from contextlib import nullcontext
from datetime import datetime

import pytest

from main import admin
from models import (
    Episode,
    EpisodeAdmin,
    WikipediaArticle,
    WikipediaArticleAdmin,
)
from wikipedia import Article

SEGADORS = Article(
    "Guerra dels Segadors",
    "https://ca.wikipedia.org/wiki/Guerra_dels_Segadors",
)


class FakeWikipedia:
    titles = {
        "Guerra dels Segadors": SEGADORS,
        "Revolta catalana": SEGADORS,
        "Felip V": Article(
            "Felip V", "https://ca.wikipedia.org/wiki/Felip_V", "", True
        ),
    }

    def lookup(self, titles):
        return {title: self.titles.get(title) for title in titles}


class TestWikipediaArticleAdmin:
    @pytest.fixture(autouse=True)
    def view(self, db_session, monkeypatch):
        monkeypatch.setattr("models.WikipediaClient", FakeWikipedia)
        view = next(
            view
            for view in admin.views
            if isinstance(view, WikipediaArticleAdmin)
        )
        monkeypatch.setattr(
            view, "session_maker", lambda: nullcontext(db_session)
        )
        self.view = view

    def save(self, title: str, model=None) -> dict:
        data = {"title": title}
        model = model or WikipediaArticle()
        is_created = model.id is None
        asyncio.run(self.view.on_model_change(data, model, is_created, None))
        return data

    def test_saves_the_article_a_title_leads_to(self):
        data = self.save(" Revolta catalana ")

        assert data == {"title": SEGADORS.title, "url": SEGADORS.url}

    def test_rejects_a_title_without_an_article(self):
        with pytest.raises(ValueError, match="cap article"):
            self.save("Guerra dels Segadorss")

    def test_rejects_disambiguation_pages(self):
        with pytest.raises(ValueError, match="desambiguació"):
            self.save("Felip V")

    def test_rejects_an_article_saved_already(self, db_session):
        saved = WikipediaArticle(title=SEGADORS.title, url=SEGADORS.url)
        db_session.add(saved)
        db_session.commit()

        with pytest.raises(ValueError, match="ja existeix"):
            self.save("Revolta catalana")
        assert self.save("Revolta catalana", saved)["title"] == SEGADORS.title


class TestEpisodeAdmin:
    def setup_method(self):
        self.view = next(
            view for view in admin.views if isinstance(view, EpisodeAdmin)
        )

    def articles_cell(self, episode: Episode):
        value = self.view.get_list_value(episode, "wikipedia_articles")
        return asyncio.run(value)[1]

    def test_lists_the_articles_of_each_episode(self):
        episode = Episode(
            title="La sardana",
            wikipedia_articles=[
                WikipediaArticle(title="Sardana", url="https://sardana"),
                WikipediaArticle(title="Cobla", url="https://cobla"),
            ],
        )

        assert self.articles_cell(episode) == ["Sardana", "Cobla"]

    def test_tells_unprocessed_episodes_from_those_without_articles(self):
        checked = Episode(
            title="Sense article", wikipedia_checked_at=datetime(2026, 10, 20)
        )
        unchecked = Episode(title="Encara no")

        assert self.articles_cell(checked) == "No hi ha articles"
        assert self.articles_cell(unchecked) == "Pendent"
