import asyncio
import hashlib
from contextlib import nullcontext
from datetime import datetime

import pytest
from sqlmodel import Session, select

from commands.create_user import set_password
from database import engine
from main import admin
from models import (
    Category,
    Episode,
    EpisodeAdmin,
    Users,
    WikipediaArticle,
    WikipediaArticleAdmin,
)
from tasks.episode_tasks import (
    generate_embeddings_task,
    link_wikipedia_articles_task,
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


class TestAdminPages:
    @pytest.fixture(autouse=True)
    def logged_in(self, client, db_session, monkeypatch):
        async def authenticate(request):
            return True

        monkeypatch.setattr(
            admin.authentication_backend, "authenticate", authenticate
        )
        for view in admin.views:
            monkeypatch.setattr(
                view, "session_maker", lambda **kw: nullcontext(db_session)
            )
        self.client = client

        sardana = WikipediaArticle(title="Sardana", url="https://sardana")
        db_session.add_all(
            [
                Episode(
                    id=1,
                    title="La sardana",
                    categories=[
                        Category(name="Música", slug="musica", type="topic")
                    ],
                    wikipedia_articles=[sardana],
                    wikipedia_checked_at=datetime(2026, 10, 20),
                ),
                Episode(
                    id=2,
                    title="Sense article",
                    wikipedia_checked_at=datetime(2026, 10, 20),
                ),
                Episode(id=3, title="Encara no"),
            ]
        )
        db_session.commit()
        self.db_session = db_session

    def test_episode_list_opens_its_menus_and_names_what_it_deletes(self):
        html = self.client.get("/admin/episode/list").text

        assert 'data-toggle="dropdown"' not in html
        assert 'id="dropdownMenuButton" data-bs-toggle="dropdown"' in html
        assert 'data-pk="La sardana"' in html
        assert "Busca articles a la Viquipèdia" in html
        assert "Regenera els vectors" in html
        assert ">Sardana</a>" in html
        assert "No hi ha articles" in html
        assert "Pendent" in html

    def test_category_list_names_what_it_deletes(self):
        html = self.client.get("/admin/category/list").text

        assert 'data-pk="Música"' in html
        # Selected rows, which the bulk delete confirmation lists.
        assert 'data-name="Música"' in html

    def test_list_shows_why_a_delete_failed(self):
        html = self.client.get("/admin/category/list?error=Boom").text

        assert 'class="alert alert-danger" role="alert">Boom</div>' in html

    def test_episode_form_leaves_the_checked_date_to_the_linking(self):
        html = self.client.get("/admin/episode/edit/1").text

        assert 'name="wikipedia_articles"' in html
        assert "wikipedia_checked_at" not in html

    def test_episode_details_names_what_it_deletes(self):
        html = self.client.get("/admin/episode/details/1").text

        assert 'data-pk="La sardana"' in html

    def test_episode_details_runs_the_actions_on_the_episode(self):
        html = self.client.get("/admin/episode/details/1").text

        assert "Busca articles a la Viquipèdia" in html
        assert "Regenera els vectors" in html
        # The confirmations' "Yes", for this episode only.
        assert 'action/relink-wikipedia?pks=1"' in html
        assert 'action/regenerate-embeddings?pks=1"' in html

    def test_relinking_clears_the_episodes_and_queues_a_search(
        self, monkeypatch
    ):
        queued = []

        def delay(episode_ids):
            # Cleared first, or the linking would skip the episode.
            episode = self.db_session.get(Episode, 1)
            queued.append((episode_ids, episode.wikipedia_checked_at))

        monkeypatch.setattr(link_wikipedia_articles_task, "delay", delay)
        referer = "http://testserver/admin/episode/list?page=2"

        response = self.client.get(
            "/admin/episode/action/relink-wikipedia?pks=1,2",
            headers={"Referer": referer},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert response.headers["location"] == referer
        self.db_session.expire_all()
        for id in (1, 2):
            episode = self.db_session.get(Episode, id)
            assert episode.wikipedia_articles == []
            assert episode.wikipedia_checked_at is None
        # The article stays for other episodes; only the link goes.
        assert self.db_session.exec(select(WikipediaArticle)).one()
        assert queued == [([1, 2], None)]

    def test_regenerating_embeddings_queues_them_for_the_episodes(
        self, monkeypatch
    ):
        queued = []
        monkeypatch.setattr(
            generate_embeddings_task,
            "delay",
            lambda **kwargs: queued.append(kwargs),
        )
        referer = "http://testserver/admin/episode/list?page=2"

        response = self.client.get(
            "/admin/episode/action/regenerate-embeddings?pks=1,3",
            headers={"Referer": referer},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert response.headers["location"] == referer
        assert queued == [{"episode_ids": [1, 3], "refresh": True}]


def legacy_hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


class TestPasswords:
    def test_hashes_new_passwords_with_argon2(self):
        user = Users(username="admin", password_hash=Users.hash_password("pa"))

        assert user.password_hash.startswith("$argon2id$")
        assert user.verify_password("pa")
        assert not user.verify_password("pb")
        assert not user.password_needs_rehash()

    def test_accepts_legacy_hashes_until_they_are_replaced(self):
        user = Users(username="admin", password_hash=legacy_hash("pa"))

        assert user.verify_password("pa")
        assert not user.verify_password("pb")
        assert user.password_needs_rehash()

    def test_rejects_a_malformed_hash(self):
        user = Users(username="admin", password_hash="$argon2id$broken")

        assert not user.verify_password("pa")


class TestLogin:
    # The login opens its own session, so the user is committed for real.
    @pytest.fixture(autouse=True)
    def user(self, client):
        with Session(engine) as session:
            user = Users(username="admin", password_hash=legacy_hash("pa"))
            session.add(user)
            session.commit()
            user_id = user.id
        self.client = client
        yield
        with Session(engine) as session:
            session.delete(session.get(Users, user_id))
            session.commit()

    def login(self, password: str):
        self.client.cookies.clear()
        return self.client.post(
            "/admin/login",
            data={"username": "admin", "password": password},
            follow_redirects=False,
        )

    def stored_hash(self) -> str:
        with Session(engine) as session:
            statement = select(Users.password_hash).where(
                Users.username == "admin"
            )
            return session.exec(statement).one()

    def test_replaces_a_legacy_hash_on_login(self):
        assert self.login("pa").status_code == 302
        assert self.stored_hash().startswith("$argon2id$")
        assert self.login("pa").status_code == 302

    def test_leaves_the_hash_alone_on_a_wrong_password(self):
        assert self.login("pb").status_code == 400
        assert self.stored_hash() == legacy_hash("pa")

    def test_other_sites_cant_send_the_session(self):
        cookie = self.login("pa").headers["set-cookie"]
        assert "samesite=strict" in cookie.lower()

    def test_a_new_password_ends_the_sessions_opened_before(self):
        self.login("pa")
        index = self.client.get("/admin/", follow_redirects=False)
        assert index.status_code == 200

        set_password("admin", "pb")

        index = self.client.get("/admin/", follow_redirects=False)
        assert index.status_code == 302
