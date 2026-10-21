"""
Link episodes to the Catalan Wikipedia articles about them.

Only looks at episodes the job hasn't checked before and nobody has linked
by hand, so edits made in the admin stay. Run weekly after classification;
run it by hand to backfill the archive, or with --dry-run to see what it
would link without saving anything.

Usage:
    python -m commands.link_wikipedia_articles --max-total 50 --dry-run
"""

import os

from openai import OpenAI
from sqlmodel import select

from database import get_session
from logger import logger
from models import Episode
from repositories import EpisodesRepository, WikipediaArticlesRepository
from services import WikipediaLinkingService
from wikipedia import WikipediaClient


def link_wikipedia_articles(
    batch_size: int = 50,
    max_total: int | None = None,
    dry_run: bool = False,
    episode_ids: list[int] | None = None,
):
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    wikipedia_client = WikipediaClient()
    total_processed = 0
    total_linked = 0
    # Failed episodes stay unchecked for the next run, but this one moves
    # past them; so does a dry run, which never marks any as checked.
    skipped: set[int] = set()

    logger.info(
        f"Starting Wikipedia linking with batch_size={batch_size}, "
        f"max_total={max_total}, dry_run={dry_run}"
    )

    while max_total is None or total_processed < max_total:
        with next(get_session()) as session:
            linker = WikipediaLinkingService(
                openai_client,
                wikipedia_client,
                EpisodesRepository(session),
                WikipediaArticlesRepository(session),
            )

            remaining = (
                None if max_total is None else max_total - total_processed
            )
            current_batch_size = (
                min(batch_size, remaining) if remaining else batch_size
            )

            query = (
                select(Episode)
                .where(Episode.wikipedia_checked_at.is_(None))
                .where(~Episode.wikipedia_articles.any())
                .where(Episode.id.not_in(list(skipped)))
                .order_by(Episode.published_at.desc(), Episode.id)
                .limit(current_batch_size)
            )
            if episode_ids is not None:
                query = query.where(Episode.id.in_(episode_ids))
            episodes = session.exec(query).all()

            if not episodes:
                logger.info("No more episodes to link")
                break

            logger.info(f"Processing batch of {len(episodes)} episodes")

            for episode in episodes:
                try:
                    articles = linker.find_articles(episode)
                except Exception as e:
                    logger.error(
                        f"Failed to find Wikipedia articles for episode "
                        f"{episode.id}: {e}"
                    )
                    skipped.add(episode.id)
                    continue

                if dry_run:
                    logger.info(
                        f"Would link episode {episode.id} "
                        f'"{episode.title}" to '
                        f"{[article.title for article in articles]}"
                    )
                    skipped.add(episode.id)
                else:
                    linker.save_articles(episode, articles)
                if articles:
                    total_linked += 1

            if dry_run:
                session.rollback()
            else:
                session.commit()

            total_processed += len(episodes)
            logger.info(
                f"Progress: {total_processed} processed, "
                f"{total_linked} with articles, {len(skipped)} skipped"
            )

            if len(episodes) < current_batch_size:
                break

    logger.info(
        f"Wikipedia linking complete: {total_linked} of {total_processed} "
        f"episodes with articles"
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Link episodes to Catalan Wikipedia articles"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Episodes committed together (default: 50)",
    )
    parser.add_argument(
        "--max-total",
        type=int,
        default=None,
        help="Maximum total episodes to process (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log the articles found without saving them",
    )

    args = parser.parse_args()
    link_wikipedia_articles(
        batch_size=args.batch_size,
        max_total=args.max_total,
        dry_run=args.dry_run,
    )
