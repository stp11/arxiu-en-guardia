import json

import requests

from database import get_session
from logger import logger
from models import Episode
from services import EpisodesService

BASE_URL = (
    "https://api.3cat.cat/audios?programaradio_id=944&ordre=-data_publicacio"
)


def backfill_images(max_items: int | None = None):
    """
    Backfills image_url for all episodes by paginating through the API.
    Only updates episodes that already exist in the database.
    """
    logger.info("Starting image backfill task.")

    with next(get_session()) as session:
        total_updated = 0
        total_processed = 0
        page = 1

        while True:
            url = f"{BASE_URL}&pagina={page}"
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()

                data = response.json().get("resposta", {})
                items = data.get("items", {}).get("item", [])

                if not items:
                    logger.info(f"No more items found on page {page}")
                    break

            except (
                requests.RequestException,
                json.JSONDecodeError,
                KeyError,
            ) as e:
                logger.error(f"Failed to fetch or parse page {page}: {e}")
                break

            for ep_data in items:
                if max_items and total_processed >= max_items:
                    break

                image_url = EpisodesService._extract_image_url(ep_data)
                total_processed += 1

                if not image_url:
                    logger.info(
                        f"No image found for episode {ep_data.get('id')}"
                    )
                    continue

                episode = session.get(Episode, ep_data["id"])
                if not episode:
                    logger.info(
                        f"Episode {ep_data['id']} not found in DB, skipping"
                    )
                    continue

                if episode.image_url == image_url:
                    logger.info(
                        f"Episode {episode.id} already has image_url set"
                    )
                    continue

                episode.image_url = image_url
                total_updated += 1

            session.commit()

            if max_items and total_processed >= max_items:
                logger.info(f"Reached max items limit ({max_items}).")
                break

            total_pages = data.get("paginacio", {}).get("total_pagines", 0)
            logger.info(f"Processed page {page}/{total_pages}")

            if page >= total_pages:
                logger.info("Reached the final page of the API.")
                break

            page += 1

        logger.info(f"Backfill complete. Updated {total_updated} episodes.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Backfill episode image URLs from the API"
    )
    parser.add_argument(
        "--max-total",
        type=int,
        default=None,
        help="Maximum total episodes to process (default: all)",
    )

    args = parser.parse_args()
    backfill_images(max_items=args.max_total)
