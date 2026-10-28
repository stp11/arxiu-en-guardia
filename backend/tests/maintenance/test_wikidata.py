import re

from maintenance.wikidata import BATCH_SIZE, WikidataClient, wikidata_items
from wikipedia import USER_AGENT

ENTITY = "http://www.wikidata.org/entity/"
PROPERTY = "http://www.wikidata.org/prop/direct/"


class FakeResponse:
    def __init__(self, data: dict):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


class FakeQueryService:
    """Answers the links query from a dict of item -> [(property, value)]."""

    def __init__(self, links=None):
        self.links = links or {}
        self.queries = []
        self.headers = {}

    def mount(self, prefix, adapter):
        pass

    def get(self, url, params, timeout):
        query = params["query"]
        self.queries.append(query)
        items, properties = re.findall(r"VALUES \?\w+ \{ ([^}]*) \}", query)
        properties = {p.removeprefix("wdt:") for p in properties.split()}
        bindings = []
        for item in items.split():
            item = item.removeprefix("wd:")
            for property, value in self.links.get(item, []):
                if property in properties:
                    bindings.append(
                        {
                            "item": {"value": ENTITY + item},
                            "property": {"value": PROPERTY + property},
                            "value": {"value": ENTITY + value},
                        }
                    )
        return FakeResponse({"results": {"bindings": bindings}})


class TestLinks:
    def test_returns_the_links_through_the_properties(self):
        service = FakeQueryService(
            {
                "Q1492": [("P131", "Q5705"), ("P17", "Q29"), ("P31", "Q515")],
                "Q90": [("P17", "Q142")],
            }
        )

        found = WikidataClient(service, pause=0).links(
            ["Q1492", "Q90", "Q404"], ["P131", "P17"]
        )

        assert found == {
            "Q1492": [("P131", "Q5705"), ("P17", "Q29")],
            "Q90": [("P17", "Q142")],
            "Q404": [],
        }

    def test_keeps_only_items(self):
        service = FakeQueryService({"Q1492": [("P131", "L123")]})

        found = WikidataClient(service, pause=0).links(["Q1492"], ["P131"])

        assert found == {"Q1492": []}

    def test_asks_for_a_batch_at_most_per_query(self):
        service = FakeQueryService()
        items = [f"Q{n}" for n in range(BATCH_SIZE * 2 + 5)]

        found = WikidataClient(service, pause=0).links(items + items[:3], [])

        assert len(found) == len(items)
        sizes = [query.count("wd:") for query in service.queries]
        assert sizes == [BATCH_SIZE, BATCH_SIZE, 5]

    def test_never_asks_for_paths(self):
        service = FakeQueryService()

        WikidataClient(service, pause=0).links(["Q1492"], ["P131", "P17"])

        # A path of any length (+ or *) is what spends the query budget.
        assert not re.search(r"[+*]\s*\?", service.queries[0])

    def test_identifies_itself(self):
        service = FakeQueryService()

        WikidataClient(service)

        assert service.headers["User-Agent"] == USER_AGENT


class FakeWikipedia:
    """Answers title queries the way the MediaWiki API does."""

    def __init__(self, pages, redirects=None):
        self.pages = pages
        self.redirects = redirects or {}
        self.requests = []

    def _query(self, **params):
        self.requests.append(params)
        query = {"pages": []}
        for title in params["titles"].split("|"):
            name = title[:1].upper() + title[1:]
            if name != title:
                query.setdefault("normalized", []).append(
                    {"from": title, "to": name}
                )
            if name in self.redirects:
                query.setdefault("redirects", []).append(
                    {"from": name, "to": self.redirects[name]}
                )
                name = self.redirects[name]
            if name in self.pages:
                query["pages"].append(
                    {"title": name, "pageprops": self.pages[name]}
                )
            else:
                query["pages"].append({"title": name, "missing": True})
        return query


class TestWikidataItems:
    def test_follows_normalization_and_redirects(self):
        wikipedia = FakeWikipedia(
            {"Barcelona": {"wikibase_item": "Q1492"}},
            redirects={"Ciutat Comtal": "Barcelona"},
        )

        found = wikidata_items(wikipedia, ["barcelona", "Ciutat Comtal"])

        assert found == {"barcelona": "Q1492", "Ciutat Comtal": "Q1492"}
        assert "wikibase_item" in wikipedia.requests[0]["ppprop"]

    def test_leaves_out_disambiguation_and_missing_pages(self):
        wikipedia = FakeWikipedia(
            {
                "Washington": {"disambiguation": "", "wikibase_item": "Q1"},
                "Sardana": {},
            }
        )

        found = wikidata_items(
            wikipedia, ["Washington", "Sardana", "Villa Diodati", "A|B"]
        )

        assert found == dict.fromkeys(
            ["Washington", "Sardana", "Villa Diodati", "A|B"]
        )
        assert wikipedia.requests[0]["titles"] == (
            "Washington|Sardana|Villa Diodati"
        )

    def test_asks_for_fifty_titles_at_most_per_request(self):
        wikipedia = FakeWikipedia({})

        wikidata_items(wikipedia, [f"Lloc {n}" for n in range(120)])

        sizes = [len(r["titles"].split("|")) for r in wikipedia.requests]
        assert sizes == [50, 50, 20]
