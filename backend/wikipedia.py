"""
Read-only client for Catalan Wikipedia's MediaWiki Action API.

Reading needs no account or key. Wikimedia asks clients to identify
themselves in the User-Agent and to send one request at a time.
"""

from collections.abc import Iterable
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_URL = "https://ca.wikipedia.org/w/api.php"
USER_AGENT = "ArxiuEnGuardia/1.0 (https://www.arxiu-en-guardia.com)"

# The most titles one query accepts from a client without the bot right.
MAX_TITLES = 50


@dataclass(frozen=True)
class Article:
    title: str
    url: str
    description: str = ""
    disambiguation: bool = False
    # Latitude and longitude, for the articles about a place.
    coordinates: tuple[float, float] | None = None


class WikipediaClient:
    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def lookup(self, titles: Iterable[str]) -> dict[str, Article | None]:
        """
        Find the article each title names, following redirects. A title
        with no article maps to None; a disambiguation page is returned,
        flagged, for the caller to decide.
        """
        found: dict[str, Article | None] = {}
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
            query = self._query(titles="|".join(batch), redirects=1)
            normalized = _renames(query.get("normalized", []))
            redirects = _renames(query.get("redirects", []))
            pages = {page["title"]: page for page in query.get("pages", [])}
            for title in batch:
                name = normalized.get(title, title)
                page = pages.get(redirects.get(name, name))
                found[title] = (
                    _article(page) if page and "pageid" in page else None
                )
        return found

    def search(self, text: str, limit: int = 5) -> list[Article]:
        """Articles matching the text, best match first."""
        query = self._query(
            generator="search",
            gsrsearch=text,
            gsrlimit=limit,
            gsrnamespace=0,
        )
        pages = sorted(query.get("pages", []), key=lambda page: page["index"])
        return [_article(page) for page in pages]

    def _query(self, **params) -> dict:
        response = self.session.get(
            API_URL,
            params={
                "action": "query",
                "format": "json",
                "formatversion": 2,
                "prop": "info|pageprops|description|coordinates",
                "inprop": "url",
                "ppprop": "disambiguation",
                # Ten for the whole query otherwise, not per page.
                "colimit": "max",
                **params,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise WikipediaError(data["error"].get("info", data["error"]))
        return data.get("query", {})


class WikipediaError(Exception):
    pass


def _renames(items: list[dict]) -> dict[str, str]:
    return {item["from"]: item["to"] for item in items}


def _article(page: dict) -> Article:
    # Only the article's primary coordinates, the place it's about.
    coordinates = page.get("coordinates", [])
    return Article(
        title=page["title"],
        url=page["fullurl"],
        description=page.get("description", ""),
        disambiguation="disambiguation" in page.get("pageprops", {}),
        coordinates=(
            (coordinates[0]["lat"], coordinates[0]["lon"])
            if coordinates
            else None
        ),
    )
