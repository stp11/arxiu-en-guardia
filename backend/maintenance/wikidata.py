"""
Read-only access to Wikidata: which item each Catalan Wikipedia article is
about, and the Wikidata Query Service for the links between items.

The service gives each client about a minute of query time per minute and
answers 429 with a Retry-After once it's spent. Only cheap queries are
sent, one at a time: the direct links of a batch of items, never a path
of any length, which is what spends that minute.
"""

import time
from collections.abc import Iterable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from wikipedia import MAX_TITLES, USER_AGENT, WikipediaClient, _renames

SPARQL_URL = "https://query.wikidata.org/sparql"

# Items per query, small enough to keep the URL short.
BATCH_SIZE = 80
# Seconds between queries.
PAUSE = 2


class WikidataClient:
    def __init__(self, session: requests.Session | None = None, pause=PAUSE):
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.session.headers["Accept"] = "application/sparql-results+json"
        # Waits as long as a 429's Retry-After says before trying again.
        retry = Retry(
            total=3,
            backoff_factor=5,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.pause = pause

    def links(
        self, items: Iterable[str], properties: Iterable[str]
    ) -> dict[str, list[tuple[str, str]]]:
        """
        The items each item links to through any of the properties, as
        (property, item) pairs, e.g. {"Q1492": [("P131", "Q5705"), ...]}.
        """
        items = list(dict.fromkeys(items))
        values = " ".join(f"wdt:{p}" for p in properties)
        found: dict[str, list[tuple[str, str]]] = {}
        for start in range(0, len(items), BATCH_SIZE):
            if start:
                time.sleep(self.pause)
            end = start + BATCH_SIZE
            batch = items[start:end]
            subjects = " ".join(f"wd:{item}" for item in batch)
            rows = self._query(
                f"SELECT ?item ?property ?value WHERE {{"
                f" VALUES ?item {{ {subjects} }}"
                f" VALUES ?property {{ {values} }}"
                f" ?item ?property ?value . FILTER(isIRI(?value)) }}"
            )
            for item in batch:
                found[item] = []
            for row in rows:
                item, property, value = (
                    _id(row[key]["value"])
                    for key in ("item", "property", "value")
                )
                # Items only: some values are lexemes or other entities.
                if value.startswith("Q"):
                    found[item].append((property, value))
        return found

    def _query(self, query: str) -> list[dict]:
        response = self.session.get(
            SPARQL_URL, params={"query": query}, timeout=60
        )
        response.raise_for_status()
        return response.json()["results"]["bindings"]


def wikidata_items(
    wikipedia: WikipediaClient, titles: Iterable[str]
) -> dict[str, str | None]:
    """
    The Wikidata item of each title's article, following redirects. Titles
    without an article, or at a disambiguation page, map to None.
    """
    found: dict[str, str | None] = {}
    # "|" separates titles in a query, and no article can contain it.
    valid = []
    for title in dict.fromkeys(titles):
        if title.strip() and "|" not in title:
            valid.append(title)
        else:
            found[title] = None

    for start in range(0, len(valid), MAX_TITLES):
        end = start + MAX_TITLES
        batch = valid[start:end]
        query = wikipedia._query(
            titles="|".join(batch),
            redirects=1,
            ppprop="disambiguation|wikibase_item",
        )
        normalized = _renames(query.get("normalized", []))
        redirects = _renames(query.get("redirects", []))
        pages = {page["title"]: page for page in query.get("pages", [])}
        for title in batch:
            name = normalized.get(title, title)
            page = pages.get(redirects.get(name, name), {})
            props = page.get("pageprops", {})
            found[title] = (
                None
                if "disambiguation" in props
                else props.get("wikibase_item")
            )
    return found


def _id(uri: str) -> str:
    return uri.rsplit("/", 1)[1]
