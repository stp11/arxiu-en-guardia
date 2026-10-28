"""
Propose removing broad locations from episodes that have a place inside them.

An episode tagged "Europa" and "París" only needs "París": the broad place
stays on the episodes that have nothing more specific. Which place is
inside which comes from Wikidata, through each location's Catalan
Wikipedia article. The proposal is written to a CSV, one row per episode
and location to remove, to review before applying it; the database is
only read. apply_location_containment, which applied the first proposal,
was removed once it had run: restore it from the history of PR #244.

Usage:
    python -m maintenance.propose_location_containment --output containment.csv
"""

import csv
from collections import defaultdict, deque
from dataclasses import dataclass, field

from sqlmodel import Session, select

from database import get_session
from logger import logger
from maintenance.wikidata import WikidataClient, wikidata_items
from models import Category, CategoryType, Episode, EpisodeCategory
from wikipedia import WikipediaClient

# Located in (an administrative division), country, continent, located on
# a physical feature, and part of.
PROPERTIES = ["P131", "P17", "P30", "P706", "P361"]

# A place is inside another only along a path in this order: divisions,
# then a country, then a continent. "Part of" and physical features only
# lead on to more of the same: their country lists every country they
# touch, and "part of" wanders off to historical states and alliances.
NEXT_STEP = {
    "division": {
        "P131": "division",
        "P361": "part",
        "P17": "country",
        "P30": "continent",
        "P706": "feature",
    },
    "part": {"P131": "part", "P361": "part"},
    "country": {"P30": "continent"},
}

# How far up from our places the climb goes, and how much further past a
# "part of" link, since few of those lead anywhere useful.
MAX_DEPTH = 6
PART_OF_DEPTH = 1

CSV_FIELDS = [
    "episode_id",
    "episode",
    "remove_id",
    "remove",
    "because_of_id",
    "because_of",
    "path",
]


@dataclass
class Location:
    id: int
    name: str
    episode_ids: set[int] = field(default_factory=set)


@dataclass
class Removal:
    episode_id: int
    episode: str
    remove: Location
    because_of: Location
    path: list[str]


def load_locations(
    session: Session,
) -> tuple[dict[int, Location], dict[int, str]]:
    """The locations with their episodes, and those episodes' titles."""
    rows = session.exec(
        select(Category.id, Category.name, Episode.id, Episode.title)
        .join(EpisodeCategory, EpisodeCategory.category_id == Category.id)
        .join(Episode, Episode.id == EpisodeCategory.episode_id)
        .where(Category.type == CategoryType.LOCATION)
    )
    locations: dict[int, Location] = {}
    titles: dict[int, str] = {}
    for id, name, episode_id, title in rows:
        locations.setdefault(id, Location(id, name)).episode_ids.add(
            episode_id
        )
        titles[episode_id] = title
    return locations, titles


def climb(
    wikidata: WikidataClient, items: set[str]
) -> dict[str, list[tuple[str, str]]]:
    """
    The links of the items and of everything above them, one level per
    round of queries.
    """
    links: dict[str, list[tuple[str, str]]] = {}
    # Levels left to climb past a "part of" link; None for no limit.
    budget: dict[str, int | None] = dict.fromkeys(items)
    level = set(items)
    for depth in range(MAX_DEPTH):
        todo = [
            item
            for item in sorted(level)
            if item not in links and (budget[item] is None or budget[item] > 0)
        ]
        if not todo:
            break
        found = wikidata.links(todo, PROPERTIES)
        links.update(found)
        level = set()
        for item in todo:
            for property, parent in found[item]:
                if budget[item] is None:
                    left = PART_OF_DEPTH if property == "P361" else None
                else:
                    left = budget[item] - 1
                if parent not in budget or _more(left, budget[parent]):
                    budget[parent] = left
                level.add(parent)
        logger.info(
            f"Level {depth + 1}: {len(todo)} items, {len(links)} in all"
        )
    return links


def _more(left: int | None, current: int | None) -> bool:
    if current is None:
        return False
    return left is None or left > current


def containers(
    links: dict[str, list[tuple[str, str]]],
    counts: dict[str, dict[str, int]],
    item: str,
) -> dict[str, list[str]]:
    """
    The places the item is inside, each with the shortest path of
    properties that leads there. counts holds how many values each item
    has per property, from count_values.
    """
    paths: dict[tuple[str, str], list[str]] = {(item, "division"): []}
    found: dict[str, list[str]] = {}
    queue = deque([(item, "division")])
    while queue:
        node, step = queue.popleft()
        for property, parent in links.get(node, []):
            following = NEXT_STEP.get(step, {}).get(property)
            if not following or not _trusted(counts[node], property):
                continue
            if (parent, following) in paths:
                continue
            path = paths[(node, step)] + [property]
            paths[(parent, following)] = path
            found.setdefault(parent, path)
            queue.append((parent, following))
    found.pop(item, None)
    return found


def count_values(
    links: dict[str, list[tuple[str, str]]],
) -> dict[str, dict[str, int]]:
    counts = {}
    for item, edges in links.items():
        counts[item] = defaultdict(int)
        for property, _ in edges:
            counts[item][property] += 1
    return counts


def _trusted(counts: dict[str, int], property: str) -> bool:
    # A range in three countries proves nothing about any of them. Several
    # divisions are all true (a town's comarca and province), unless the
    # place spans several countries.
    if property in ("P131", "P361"):
        return counts["P17"] <= 1
    return counts[property] == 1


def propose(
    locations: dict[int, Location],
    titles: dict[int, str],
    items: dict[int, str],
    links: dict[str, list[tuple[str, str]]],
) -> list[Removal]:
    counts = count_values(links)
    inside = {
        id: containers(links, counts, item) for id, item in items.items()
    }
    by_episode: dict[int, list[int]] = defaultdict(list)
    for location in locations.values():
        for episode_id in location.episode_ids:
            by_episode[episode_id].append(location.id)

    removals = []
    for episode_id, ids in by_episode.items():
        ids = sorted(id for id in ids if id in items)
        inners = defaultdict(list)
        for outer in ids:
            for inner in ids:
                if inner != outer and items[outer] in inside[inner]:
                    # Two names for the same place: neither goes.
                    if items[inner] not in inside[outer]:
                        inners[outer].append(inner)
        for outer, candidates in inners.items():
            # Explained by a place the episode keeps, so it's never left
            # without one.
            kept = [id for id in candidates if id not in inners]
            if not kept:
                continue
            inner = kept[0]
            removals.append(
                Removal(
                    episode_id,
                    titles[episode_id],
                    locations[outer],
                    locations[inner],
                    inside[inner][items[outer]],
                )
            )
    return removals


def write_csv(path: str, removals: list[Removal]) -> None:
    # Grouped by the place removed, so a wrong rule is one block to delete.
    removals = sorted(
        removals,
        key=lambda r: (
            r.remove.name.lower(),
            r.because_of.name.lower(),
            r.episode.lower(),
        ),
    )
    # utf-8-sig so spreadsheet apps detect the encoding of the accents.
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for removal in removals:
            writer.writerow(
                {
                    "episode_id": removal.episode_id,
                    "episode": removal.episode,
                    "remove_id": removal.remove.id,
                    "remove": removal.remove.name,
                    "because_of_id": removal.because_of.id,
                    "because_of": removal.because_of.name,
                    "path": "/".join(removal.path),
                }
            )


def propose_location_containment(
    output: str,
    wikipedia: WikipediaClient | None = None,
    wikidata: WikidataClient | None = None,
) -> None:
    wikipedia = wikipedia or WikipediaClient()
    wikidata = wikidata or WikidataClient()

    with next(get_session()) as session:
        locations, titles = load_locations(session)
        session.rollback()

    # Only places that share an episode with another place can go.
    shared = defaultdict(int)
    for location in locations.values():
        for episode_id in location.episode_ids:
            shared[episode_id] += 1
    candidates = [
        location
        for location in locations.values()
        if any(shared[id] > 1 for id in location.episode_ids)
    ]
    found = wikidata_items(wikipedia, (c.name for c in candidates))
    items = {c.id: found[c.name] for c in candidates if found[c.name]}
    logger.info(
        f"{len(candidates)} locations share an episode, "
        f"{len(items)} with a Wikidata item"
    )

    links = climb(wikidata, set(items.values()))
    removals = propose(locations, titles, items, links)
    write_csv(output, removals)

    episodes = {removal.episode_id for removal in removals}
    logger.info(
        f"Proposed {len(removals)} removals on {len(episodes)} episodes"
    )
    logger.info(f"Wrote {output}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Propose removing broad locations into a CSV, for review"
    )
    parser.add_argument(
        "--output",
        default="location_containment.csv",
        help="CSV file to write (default: location_containment.csv)",
    )

    args = parser.parse_args()
    propose_location_containment(output=args.output)
