import os

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


def _episode_embedding_text(episode: Episode) -> str:
    parts: list[str] = [episode.title]
    if episode.description:
        parts.append(episode.description)

    by_type: dict[str, list[str]] = {}
    for category in episode.categories:
        key = category.type.value if category.type else "other"
        by_type.setdefault(key, []).append(category.name)

    for type_key, names in by_type.items():
        label = CATEGORY_TYPE_LABELS.get(type_key, type_key)
        parts.append(f"{label}: {', '.join(names)}")

    return " | ".join(parts).replace("\n", " ")


def backfill_embeddings(batch_size: int = 100, max_total: int = None):
    """Generate embeddings for episodes that don't have one yet."""

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    total_processed = 0

    logger.info(
        f"Starting embedding backfill with batch_size={batch_size}, "
        f"max_total={max_total}"
    )

    while max_total is None or total_processed < max_total:
        with next(get_session()) as session:
            remaining = (
                None if max_total is None else max_total - total_processed
            )
            current_batch_size = (
                min(batch_size, remaining) if remaining else batch_size
            )

            episodes = session.exec(
                select(Episode)
                .where(Episode.description.isnot(None))
                .where(Episode.embedding.is_(None))
                .order_by(Episode.published_at.desc())
                .limit(current_batch_size)
            ).all()

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

    args = parser.parse_args()
    backfill_embeddings(batch_size=args.batch_size, max_total=args.max_total)
