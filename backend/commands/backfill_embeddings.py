import html
import os
import re

from openai import OpenAI
from sqlmodel import select

from database import get_session
from logger import logger
from models import Episode

EMBEDDING_MODEL = "text-embedding-3-small"

CATEGORY_TYPE_LABELS = {
    "topic": "Temes",
    "location": "Llocs",
    "character": "Personatges",
    "time_period": "Època",
}


# What 3Cat repeats in every episode would otherwise pull episodes together
# for their format rather than their topic.
EPISODE_NUMBER = re.compile(r"^\d+\s*-\s*")
# "Capítol 1308. ", "Capítol 1.000 - Tercera part. ", "Capítol 715 - "...
CHAPTER_NUMBER = re.compile(
    r"^Capítol(?: [\d.]+)?(?:\s*-\s*\w+ part)?\s*[.-]\s*"
)
# The description of the early episodes.
PLACEHOLDER = "En guàrdia"
# From the sentence that introduces the guests, "En parlem amb Josep M. Solé
# i Sabaté, historiador, i...", to the end: their names and posts.
GUESTS = re.compile(
    r"[^.?!]*\b(?:[Pp]arlem amb|En parlen|Josep M(?:aria|\.)? Solé(?: i)? "
    r"Sabat[eé])\b.*",
    re.S,
)
# Though the books and theses the guests wrote usually name it.
QUOTED = re.compile(r"[\"“«]([^\"”»]+)[\"”»]")
HTML_TAG = re.compile(r"<[^>]+>")


def _clean_description(description: str) -> str:
    text = HTML_TAG.sub("", html.unescape(description)).strip()
    if text == PLACEHOLDER:
        return ""
    text = EPISODE_NUMBER.sub("", CHAPTER_NUMBER.sub("", text))
    guests = GUESTS.search(text)
    if guests:
        titles = QUOTED.findall(guests.group())
        text = " ".join([text[: guests.start()], *titles])
    return " ".join(text.split())


def _episode_embedding_text(episode: Episode) -> str:
    parts: list[str] = [EPISODE_NUMBER.sub("", episode.title).strip()]
    description = _clean_description(episode.description or "")
    if description:
        parts.append(description)

    by_type: dict[str, list[str]] = {}
    for category in episode.categories:
        key = category.type.value if category.type else "other"
        by_type.setdefault(key, []).append(category.name)

    for type_key, names in by_type.items():
        label = CATEGORY_TYPE_LABELS.get(type_key, type_key)
        parts.append(f"{label}: {', '.join(names)}")

    return " | ".join(parts).replace("\n", " ")


def backfill_embeddings(
    batch_size: int = 100,
    max_total: int = None,
    refresh: bool = False,
    episode_ids: list[int] | None = None,
):
    """
    Generate embeddings for episodes that don't have one yet, or for every
    episode with refresh: the text includes category names, so vectors go
    stale when categories are merged, renamed or added. episode_ids limits
    either to those episodes.
    """

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    total_processed = 0

    logger.info(
        f"Starting embedding backfill with batch_size={batch_size}, "
        f"max_total={max_total}, refresh={refresh}, "
        f"episode_ids={episode_ids}"
    )

    while max_total is None or total_processed < max_total:
        with next(get_session()) as session:
            remaining = (
                None if max_total is None else max_total - total_processed
            )
            current_batch_size = (
                min(batch_size, remaining) if remaining else batch_size
            )

            # Episodes without a description too, from their title and
            # categories: otherwise they have no similar episodes at all.
            query = (
                select(Episode)
                .order_by(Episode.published_at.desc(), Episode.id)
                .limit(current_batch_size)
            )
            if episode_ids is not None:
                query = query.where(Episode.id.in_(episode_ids))
            if refresh:
                # Refreshed episodes still match, so page past them.
                query = query.offset(total_processed)
            else:
                query = query.where(Episode.embedding.is_(None))
            episodes = session.exec(query).all()

            if not episodes:
                logger.info("No more episodes to embed")
                break

            logger.info(f"Processing batch of {len(episodes)} episodes")

            texts = [_episode_embedding_text(ep) for ep in episodes]

            try:
                response = client.embeddings.create(
                    input=texts, model=EMBEDDING_MODEL
                )

                for ep, item in zip(episodes, response.data):
                    ep.embedding = item.embedding

                session.commit()
                total_processed += len(episodes)
                logger.info(
                    f"Committed batch of {len(episodes)} embeddings. "
                    f"Total: {total_processed}"
                )

            except Exception as e:
                logger.error(f"Failed to generate embeddings: {e}")
                session.rollback()
                break

            if len(episodes) < current_batch_size:
                break

    logger.info(f"Embedding backfill complete. Total: {total_processed}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate embeddings for episodes using OpenAI"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of episodes per API call (default: 100)",
    )
    parser.add_argument(
        "--max-total",
        type=int,
        default=None,
        help="Maximum total episodes to process (default: all)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-embed every episode, not only those without an embedding",
    )

    args = parser.parse_args()
    backfill_embeddings(
        batch_size=args.batch_size,
        max_total=args.max_total,
        refresh=args.refresh,
    )
