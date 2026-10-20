from itertools import count
from urllib.parse import quote

import pytest

from wikipedia import USER_AGENT, Article, WikipediaClient, WikipediaError


class FakeResponse:
    def __init__(self, data: dict):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


class FakeWiki:
    """Answers queries the way the MediaWiki API does, from a few pages."""

    def __init__(self, pages=None, redirects=None, results=None):
        self.pages = pages or {}
        self.redirects = redirects or {}
        self.results = results or {}
        self.ids = count(1)
        self.requests = []
        self.headers = {}

    def mount(self, prefix, adapter):
        pass

    def get(self, url, params, timeout):
        self.requests.append(params)
        if "titles" in params:
            return FakeResponse(self._titles(params["titles"].split("|")))
        titles = self.results.get(params["gsrsearch"], [])
        pages = [
            {**self._page(title), "index": index}
            for index, title in enumerate(titles, start=1)
        ]
        # The API lists results in no particular order, ranked by index.
        return FakeResponse({"query": {"pages": pages[::-1]}})

    def _titles(self, titles: list[str]) -> dict:
        query = {"pages": []}
        for title in titles:
            name = title.replace("_", " ")
            name = name[:1].upper() + name[1:]
            if name != title:
                query.setdefault("normalized", []).append(
                    {"from": title, "to": name}
                )
            if "[" in name:
                query["pages"].append({"title": name, "invalid": True})
                continue
            if name in self.redirects:
                query.setdefault("redirects", []).append(
                    {"from": name, "to": self.redirects[name]}
                )
                name = self.redirects[name]
            query["pages"].append(self._page(name))
        return {"batchcomplete": True, "query": query}

    def _page(self, title: str) -> dict:
        page = {
            "ns": 0,
            "title": title,
            "fullurl": "https://ca.wikipedia.org/wiki/"
            + quote(title.replace(" ", "_")),
        }
        if title not in self.pages:
            return {**page, "missing": True}
        return {**page, "pageid": next(self.ids), **self.pages[title]}


SEGADORS = {"description": "(1640-1659) conflicte armat"}
DISAMBIGUATION = {
    "description": "pàgina de desambiguació de Wikimedia",
    "pageprops": {"disambiguation": ""},
}


class TestLookup:
    def test_follows_normalization_and_redirects(self):
        wiki = FakeWiki(
            pages={
                "Guerra dels Segadors": SEGADORS,
                "Jaume el Conqueridor": {},
            },
            redirects={"Jaume I": "Jaume el Conqueridor"},
        )

        found = WikipediaClient(wiki).lookup(
            ["guerra_dels Segadors", "Jaume I"]
        )

        assert found["guerra_dels Segadors"] == Article(
            title="Guerra dels Segadors",
            url="https://ca.wikipedia.org/wiki/Guerra_dels_Segadors",
            description="(1640-1659) conflicte armat",
        )
        assert found["Jaume I"].title == "Jaume el Conqueridor"
        assert found["Jaume I"].description == ""

    def test_maps_titles_without_an_article_to_none(self):
        wiki = FakeWiki()

        found = WikipediaClient(wiki).lookup(["Sense article", "[x]"])

        assert found == {"Sense article": None, "[x]": None}

    def test_never_sends_titles_a_query_cannot_hold(self):
        wiki = FakeWiki(pages={"Sardana": {}})

        found = WikipediaClient(wiki).lookup(
            ["Sardana|Mahoma", " ", "Sardana"]
        )

        assert found["Sardana|Mahoma"] is None
        assert found[" "] is None
        assert found["Sardana"].title == "Sardana"
        assert [r["titles"] for r in wiki.requests] == ["Sardana"]

    def test_flags_disambiguation_pages(self):
        wiki = FakeWiki(pages={"Felip V": DISAMBIGUATION})

        found = WikipediaClient(wiki).lookup(["Felip V"])

        assert found["Felip V"].disambiguation

    def test_asks_for_fifty_titles_at_most_per_request(self):
        wiki = FakeWiki()
        titles = [f"Article {n}" for n in range(120)]

        found = WikipediaClient(wiki).lookup(titles + titles[:10])

        assert len(found) == 120
        sizes = [len(r["titles"].split("|")) for r in wiki.requests]
        assert sizes == [50, 50, 20]

    def test_identifies_itself(self):
        wiki = FakeWiki()

        WikipediaClient(wiki)

        assert wiki.headers["User-Agent"] == USER_AGENT

    def test_raises_api_errors(self):
        wiki = FakeWiki()
        wiki.get = lambda url, params, timeout: FakeResponse(
            {"error": {"code": "badvalue", "info": "Unrecognized value"}}
        )

        with pytest.raises(WikipediaError, match="Unrecognized value"):
            WikipediaClient(wiki).lookup(["Sardana"])


class TestSearch:
    def test_returns_results_best_first(self):
        wiki = FakeWiki(
            pages={
                "Guerra de Successió": DISAMBIGUATION,
                "Guerra de Successió Espanyola": {"description": "1701–1714"},
            },
            results={
                "Guerra de Successió": [
                    "Guerra de Successió",
                    "Guerra de Successió Espanyola",
                ]
            },
        )

        results = WikipediaClient(wiki).search("Guerra de Successió", limit=3)

        assert [article.title for article in results] == [
            "Guerra de Successió",
            "Guerra de Successió Espanyola",
        ]
        assert results[0].disambiguation
        assert results[1].description == "1701–1714"
        assert wiki.requests[0]["gsrlimit"] == 3
        assert wiki.requests[0]["gsrnamespace"] == 0
