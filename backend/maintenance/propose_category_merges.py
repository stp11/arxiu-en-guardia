"""
Propose a consolidation of the categories, to review before applying it.

For every category, finds candidate duplicates (the nearest names by
embedding, plus the categories that share its episodes) and asks an LLM
whether to keep it, merge it into a duplicate, delete it, or roll it up:
keep it and also tag its episodes with a broader category. The proposal
is written to a CSV; the database is only read.

Usage:
    python -m maintenance.propose_category_merges --output merges.csv
"""

import csv
import json
import os
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from openai import OpenAI
from sqlalchemy import text
from sqlmodel import Session, select

from database import get_session
from logger import logger
from maintenance.category_review_prompts import (
    CATEGORY_REVIEW_SCHEMA,
    category_review_prompt,
)
from models import Category, CategoryType, Episode, EpisodeCategory
from services import CATEGORY_TYPE_TO_KEY

EMBEDDING_MODEL = "text-embedding-3-small"
REVIEW_MODEL = "gpt-6-luna"

NEAREST_NAMES = 8
CO_OCCURRING = 5
SAMPLE_TITLES = 3

# Well-used topics and locations, offered to every category as roll-up
# targets: a battle rarely shares an episode, or a name, with its war.
GENERAL_TYPES = (CategoryType.TOPIC, CategoryType.LOCATION)
GENERAL_MIN_EPISODES = 3

TARGET_ACTIONS = ("merge", "rollup")
KEY_TO_CATEGORY_TYPE = {
    key: type for type, key in CATEGORY_TYPE_TO_KEY.items()
}
UNTYPED_KEY = "sense tipus"

CSV_FIELDS = [
    "id",
    "type",
    "name",
    "episodes",
    "action",
    "target_id",
    "target_name",
    "target_type",
    "new_name",
    "new_type",
    "reason",
    "titles",
]


@dataclass
class CategoryInfo:
    id: int
    name: str
    type: CategoryType | None
    episode_ids: set[int] = field(default_factory=set)
    titles: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return CATEGORY_TYPE_TO_KEY.get(self.type, UNTYPED_KEY)


@dataclass
class Decision:
    action: str
    reason: str
    target_id: int | None = None
    new_name: str | None = None
    new_type: CategoryType | None = None


def load_categories(session: Session) -> dict[int, CategoryInfo]:
    categories = {
        category.id: CategoryInfo(category.id, category.name, category.type)
        for category in session.exec(select(Category))
    }
    links = session.exec(
        select(EpisodeCategory.category_id, Episode.id, Episode.title)
        .join(Episode, Episode.id == EpisodeCategory.episode_id)
        .order_by(Episode.published_at.desc())
    )
    for category_id, episode_id, title in links:
        category = categories[category_id]
        category.episode_ids.add(episode_id)
        if len(category.titles) < SAMPLE_TITLES:
            category.titles.append(title)
    return categories


def embed_names(
    client: OpenAI, categories: list[CategoryInfo], batch_size: int = 500
) -> dict[int, list[float]]:
    embeddings = {}
    for batch in _batched(categories, batch_size):
        response = client.embeddings.create(
            input=[f"{category.key}: {category.name}" for category in batch],
            model=EMBEDDING_MODEL,
        )
        for category, item in zip(batch, response.data):
            embeddings[category.id] = item.embedding
    return embeddings


def nearest_names(
    session: Session,
    embeddings: dict[int, list[float]],
    limit: int = NEAREST_NAMES,
) -> dict[int, list[int]]:
    # pgvector ranks the neighbours from a temp table, which the caller's
    # rollback drops along with everything else in the transaction.
    connection = session.connection()
    connection.execute(
        text(
            "CREATE TEMP TABLE category_name_embedding "
            "(id integer PRIMARY KEY, embedding vector)"
        )
    )
    connection.execute(
        text(
            "INSERT INTO category_name_embedding "
            "VALUES (:id, CAST(:embedding AS vector))"
        ),
        [
            {"id": id, "embedding": str(embedding)}
            for id, embedding in embeddings.items()
        ],
    )
    rows = connection.execute(
        text(
            """
            SELECT category.id, neighbour.id
            FROM category_name_embedding AS category
            CROSS JOIN LATERAL (
                SELECT other.id, category.embedding <=> other.embedding
                    AS distance
                FROM category_name_embedding AS other
                WHERE other.id <> category.id
                ORDER BY distance
                LIMIT :limit
            ) AS neighbour
            ORDER BY category.id, neighbour.distance
            """
        ),
        {"limit": limit},
    )
    neighbours = defaultdict(list)
    for id, neighbour_id in rows:
        neighbours[id].append(neighbour_id)
    return neighbours


def co_occurring(
    categories: dict[int, CategoryInfo], limit: int = CO_OCCURRING
) -> dict[int, list[int]]:
    by_episode = defaultdict(list)
    for category in categories.values():
        for episode_id in category.episode_ids:
            by_episode[episode_id].append(category.id)

    result = {}
    for category in categories.values():
        shared = Counter(
            other
            for episode_id in category.episode_ids
            for other in by_episode[episode_id]
            if other != category.id
        )
        # Among equally shared categories prefer the broader ones: they are
        # the roll-up targets.
        ranked = sorted(
            shared,
            key=lambda other: (
                -shared[other],
                -len(categories[other].episode_ids),
                other,
            ),
        )
        result[category.id] = ranked[:limit]
    return result


def review_batch(
    client: OpenAI,
    batch: list[CategoryInfo],
    categories: dict[int, CategoryInfo],
    candidates: dict[int, list[int]],
    general: list[CategoryInfo],
) -> dict[int, dict]:
    items = [
        {
            **_prompt_category(category),
            "titles": category.titles,
            "candidates": [
                _prompt_category(categories[id])
                for id in candidates[category.id]
            ],
        }
        for category in batch
    ]
    try:
        response = client.chat.completions.create(
            model=REVIEW_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": category_review_prompt(
                        items, [_prompt_category(c) for c in general]
                    ),
                }
            ],
            # Luna's default; a one-off review is worth the extra reasoning
            reasoning_effort="medium",
            response_format={
                "type": "json_schema",
                "json_schema": CATEGORY_REVIEW_SCHEMA,
            },
        )
        decisions = json.loads(response.choices[0].message.content)[
            "decisions"
        ]
    except Exception as e:
        logger.error(
            f"Failed to review categories {[c.id for c in batch]}: {e}"
        )
        return {}

    batch_ids = {category.id for category in batch}
    logger.info(f"Reviewed {len(batch)} categories")
    return {d["id"]: d for d in decisions if d["id"] in batch_ids}


def _prompt_category(category: CategoryInfo) -> dict:
    return {
        "id": category.id,
        "name": category.name,
        "key": category.key,
        "episodes": len(category.episode_ids),
    }


def to_decision(
    category: CategoryInfo, raw: dict | None, allowed_targets: set[int]
) -> Decision:
    if raw is None:
        return Decision("keep", "Sense revisió: el model no ha respost")

    action, reason = raw["action"], raw["reason"]
    if action in TARGET_ACTIONS:
        if raw["target_id"] not in allowed_targets - {category.id}:
            return Decision(
                "keep",
                f"Destí {raw['target_id']} fora dels candidats, revisa-ho. "
                f"{reason}",
            )
        return Decision(action, reason, target_id=raw["target_id"])

    if action == "keep":
        new_name = raw["new_name"] or None
        new_type = KEY_TO_CATEGORY_TYPE.get(raw["new_type"])
        return Decision(
            "keep",
            reason,
            new_name=new_name if new_name != category.name else None,
            new_type=new_type if new_type != category.type else None,
        )

    return Decision(action, reason)


def resolve(
    decisions: dict[int, Decision], categories: dict[int, CategoryInfo]
) -> None:
    """Point every merge and rollup at a category that survives."""
    _merge_renames_into_existing(decisions, categories)
    _resolve_merges(decisions, categories)
    _resolve_rollups(decisions, categories)


def _resolve_merges(
    decisions: dict[int, Decision], categories: dict[int, CategoryInfo]
) -> None:
    for id in sorted(decisions):
        path = []
        current = id
        while decisions[current].action == "merge" and current not in path:
            path.append(current)
            current = decisions[current].target_id

        if current in path:
            # A ring of merges: keep its biggest category, merge the rest.
            ring_start = path.index(current)
            ring = path[ring_start:]
            current = max(
                ring, key=lambda i: (len(categories[i].episode_ids), -i)
            )
            decisions[current] = Decision(
                "keep", "Destí comú d'un cicle de fusions"
            )

        target = categories[current]
        for member in path:
            if member == current:
                continue
            if decisions[current].action == "delete":
                decisions[member] = Decision(
                    "keep",
                    f'El destí "{target.name}" s\'elimina, revisa-ho. '
                    f"{decisions[member].reason}",
                )
            else:
                decisions[member].target_id = current


def _resolve_rollups(
    decisions: dict[int, Decision], categories: dict[int, CategoryInfo]
) -> None:
    # Merges point at their survivor by now, one step away at most.
    for id in sorted(decisions):
        decision = decisions[id]
        if decision.action != "rollup":
            continue
        target = decision.target_id
        if decisions[target].action == "merge":
            target = decisions[target].target_id
        if target == id or decisions[target].action == "delete":
            broader = categories[decision.target_id]
            decisions[id] = Decision(
                "keep",
                f"La categoria general \"{broader.name}\" s'elimina o s'hi "
                f"fusiona, revisa-ho. {decision.reason}",
            )
        else:
            decision.target_id = target

    # Rollups chain (a district, its city, its region), but must not loop.
    for id in sorted(decisions):
        path = []
        current = id
        while decisions[current].action == "rollup" and current not in path:
            path.append(current)
            current = decisions[current].target_id
        if current in path:
            decisions[current] = Decision(
                "keep",
                "Tanca un cicle d'agrupacions, revisa-ho. "
                f"{decisions[current].reason}",
            )


def _merge_renames_into_existing(
    decisions: dict[int, Decision], categories: dict[int, CategoryInfo]
) -> None:
    # Slugs are unique, so a rename onto another category's name is a merge.
    owners = {
        Category.slugify_name(category.name): category.id
        for category in categories.values()
    }
    for id in sorted(decisions):
        decision = decisions[id]
        if decision.new_name is None:
            continue
        owner = owners.setdefault(Category.slugify_name(decision.new_name), id)
        if owner != id:
            decisions[id] = Decision(
                "merge",
                f'El nom nou "{decision.new_name}" ja existeix. '
                f"{decision.reason}",
                target_id=owner,
            )


def write_csv(
    path: str,
    decisions: dict[int, Decision],
    categories: dict[int, CategoryInfo],
) -> None:
    rows = []
    for id, decision in decisions.items():
        category = categories[id]
        target = categories.get(decision.target_id)
        rows.append(
            {
                "id": id,
                "type": _type_value(category.type),
                "name": category.name,
                "episodes": len(category.episode_ids),
                "action": decision.action,
                "target_id": decision.target_id or "",
                "target_name": target.name if target else "",
                "target_type": _type_value(target.type) if target else "",
                "new_name": decision.new_name or "",
                "new_type": _type_value(decision.new_type),
                "reason": decision.reason,
                "titles": " | ".join(category.titles),
            }
        )

    # Each surviving category followed by the ones merging into it.
    def group(row: dict) -> tuple:
        if row["action"] == "merge":
            return (row["target_type"], row["target_name"].lower(), 1)
        name = row["new_name"] or row["name"]
        return (row["new_type"] or row["type"], name.lower(), 0)

    rows.sort(key=lambda row: (*group(row), row["name"].lower()))

    # utf-8-sig so spreadsheet apps detect the encoding of the accents.
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _batched(items: list, size: int) -> list[list]:
    batches = []
    for start in range(0, len(items), size):
        end = start + size
        batches.append(items[start:end])
    return batches


def _type_value(type: CategoryType | None) -> str:
    return type.value if type else ""


def propose_category_merges(
    output: str, batch_size: int = 20, workers: int = 4
) -> None:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    with next(get_session()) as session:
        categories = load_categories(session)
        used = sorted(
            (c for c in categories.values() if c.episode_ids),
            key=lambda c: (c.key, c.name.lower()),
        )
        logger.info(
            f"Loaded {len(categories)} categories, {len(used)} with episodes"
        )
        embeddings = embed_names(client, used)
        names = nearest_names(session, embeddings)
        session.rollback()

    shared = co_occurring(categories)
    candidates = {
        c.id: list(dict.fromkeys(names[c.id] + shared[c.id])) for c in used
    }
    general = [
        c
        for c in used
        if c.type in GENERAL_TYPES
        and len(c.episode_ids) >= GENERAL_MIN_EPISODES
    ]

    # Batches follow name order, so variants of a name are reviewed together.
    batches = _batched(used, batch_size)
    logger.info(f"Reviewing in {len(batches)} batches")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = pool.map(
            lambda batch: review_batch(
                client, batch, categories, candidates, general
            ),
            batches,
        )
        raw = {id: d for result in results for id, d in result.items()}

    decisions = {
        c.id: Decision("delete", "Sense episodis")
        for c in categories.values()
        if not c.episode_ids
    }
    general_ids = {c.id for c in general}
    for category in used:
        decisions[category.id] = to_decision(
            category,
            raw.get(category.id),
            set(candidates[category.id]) | general_ids,
        )
    resolve(decisions, categories)
    write_csv(output, decisions, categories)

    actions = Counter(decision.action for decision in decisions.values())
    remaining = Counter(
        _type_value(decision.new_type or categories[id].type)
        for id, decision in decisions.items()
        if decision.action in ("keep", "rollup")
    )
    logger.info(f"Proposed actions: {dict(actions)}")
    logger.info(
        f"{len(decisions)} categories now, {remaining.total()} after "
        f"applying: {dict(remaining)}"
    )
    logger.info(f"Wrote {output}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Propose category merges into a CSV, for review"
    )
    parser.add_argument(
        "--output",
        default="category_merges.csv",
        help="CSV file to write (default: category_merges.csv)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=20,
        help="Categories reviewed per LLM call (default: 20)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Concurrent LLM calls (default: 4)",
    )

    args = parser.parse_args()
    propose_category_merges(
        output=args.output, batch_size=args.batch_size, workers=args.workers
    )
