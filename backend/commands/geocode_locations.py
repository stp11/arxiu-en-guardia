"""
Place the location categories on the map, at the coordinates of their
Catalan Wikipedia articles.

Only looks at locations the job hasn't looked up before and nobody has
placed by hand, so edits made in the admin stay. Run weekly after the
Wikipedia linking; run it by hand to backfill the archive, or with
--dry-run to see where it would place them without saving anything.

Usage:
    python -m commands.geocode_locations --dry-run
"""

from sqlmodel import select

from database import get_session
from logger import logger
from models import Category, CategoryType
from services import GeocodingService
from wikipedia import WikipediaClient


def geocode_locations(dry_run: bool = False):
    with next(get_session()) as session:
        locations = session.exec(
            select(Category)
            .where(Category.type == CategoryType.LOCATION)
            .where(Category.geocoded_at.is_(None))
            .order_by(Category.name)
        ).all()
        logger.info(f"Geocoding {len(locations)} locations, dry_run={dry_run}")

        unplaced = GeocodingService(WikipediaClient()).geocode(locations)
        unplaced_ids = {location.id for location in unplaced}
        for location in locations:
            if location.id not in unplaced_ids:
                logger.info(
                    f'{"Would place" if dry_run else "Placed"} '
                    f'"{location.name}" at '
                    f"{location.latitude}, {location.longitude}"
                )
        if unplaced:
            # For the admin to place by hand, or leave off the map.
            logger.info(
                f"No coordinates for "
                f"{[location.name for location in unplaced]}"
            )

        if dry_run:
            session.rollback()
        else:
            session.commit()

    logger.info(
        f"Geocoding complete: {len(locations) - len(unplaced)} of "
        f"{len(locations)} locations placed"
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Place location categories at their Wikipedia coordinates"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log the coordinates found without saving them",
    )

    args = parser.parse_args()
    geocode_locations(dry_run=args.dry_run)
