"""
Apply a reviewed proposal from propose_location_containment.

Checks the CSV against the database, then removes each row's location
from its episode in a single transaction. A row is refused when its
episode or locations have changed since the proposal, or when the place
that explains it would be gone too. Without --apply everything is rolled
back and only the outcome is reported.

Usage:
    python -m maintenance.apply_location_containment containment.csv
    python -m maintenance.apply_location_containment containment.csv --apply
"""

import csv
import sys
from dataclasses import dataclass

from sqlalchemy import delete, func, tuple_
from sqlmodel import Session, select

from database import get_session
from logger import logger
from models import Category, Episode, EpisodeCategory

REQUIRED_COLUMNS = {
    "episode_id",
    "remove_id",
    "remove",
    "because_of_id",
    "because_of",
}


class InvalidProposal(Exception):
    def __init__(self, errors: list[str]):
        super().__init__(f"{len(errors)} problems in the proposal")
        self.errors = errors


@dataclass
class Row:
    line: int
    episode_id: int
    remove_id: int
    remove: str
    because_of_id: int
    because_of: str


def read_rows(path: str) -> list[Row]:
    with open(path, newline="", encoding="utf-8-sig") as file:
        # Spreadsheets in a Catalan or Spanish locale save with semicolons.
        sniffed = csv.Sniffer().sniff(file.readline(), delimiters=",;\t")
        file.seek(0)
        reader = csv.DictReader(file, delimiter=sniffed.delimiter)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise InvalidProposal(
                [f"Missing columns: {', '.join(sorted(missing))}"]
            )

        rows, errors = [], []
        for line, raw in enumerate(reader, start=2):
            try:
                rows.append(
                    Row(
                        line,
                        _parse_id(raw["episode_id"], "episode_id"),
                        _parse_id(raw["remove_id"], "remove_id"),
                        raw["remove"],
                        _parse_id(raw["because_of_id"], "because_of_id"),
                        raw["because_of"],
                    )
                )
            except ValueError as e:
                errors.append(f"Line {line}: {e}")

    if errors:
        raise InvalidProposal(errors)
    return rows


def _parse_id(value: str, column: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{column} {value!r} is not a number")


def check_rows(session: Session, rows: list[Row]) -> list[tuple[int, int]]:
    """The (episode, location) links to remove, once every row checks out."""
    names = dict(session.exec(select(Category.id, Category.name)).all())
    episode_ids = {row.episode_id for row in rows}
    existing = set(
        session.exec(select(Episode.id).where(Episode.id.in_(episode_ids)))
    )
    linked = set(
        session.exec(
            select(
                EpisodeCategory.episode_id, EpisodeCategory.category_id
            ).where(EpisodeCategory.episode_id.in_(episode_ids))
        ).all()
    )
    removed = {(row.episode_id, row.remove_id): row for row in rows}

    errors = []
    for row in rows:
        error = _check(row, names, existing, linked, removed)
        if error:
            errors.append(f"Line {row.line}: {error}")
    if errors:
        raise InvalidProposal(errors)
    return list(removed)


def _check(row, names, existing, linked, removed) -> str | None:
    if removed[(row.episode_id, row.remove_id)] is not row:
        return f"episode {row.episode_id} loses {row.remove!r} twice"
    if row.episode_id not in existing:
        return f"episode {row.episode_id} no longer exists"
    for id, name in [
        (row.remove_id, row.remove),
        (row.because_of_id, row.because_of),
    ]:
        if id not in names:
            return f"location {id} ({name!r}) no longer exists"
        if names[id] != name:
            return f"location {id} is named {names[id]!r} now, not {name!r}"
        if (row.episode_id, id) not in linked:
            return f"episode {row.episode_id} no longer has {name!r}"
    if row.remove_id == row.because_of_id:
        return f"{row.remove!r} can't be inside itself"
    if (row.episode_id, row.because_of_id) in removed:
        return (
            f"{row.because_of!r}, which explains removing {row.remove!r}, "
            f"is removed from episode {row.episode_id} too"
        )
    return None


def _links(session: Session) -> int:
    return session.exec(select(func.count(EpisodeCategory.episode_id))).one()


def apply_location_containment(path: str, apply: bool = False) -> None:
    rows = read_rows(path)

    with next(get_session()) as session:
        links = check_rows(session, rows)
        before = _links(session)
        if links:
            session.exec(
                delete(EpisodeCategory).where(
                    tuple_(
                        EpisodeCategory.episode_id,
                        EpisodeCategory.category_id,
                    ).in_(links)
                )
            )
        after = _links(session)

        episodes = {episode_id for episode_id, _ in links}
        logger.info(
            f"Removed {len(links)} locations from {len(episodes)} episodes"
        )
        logger.info(f"Episode links: {before} -> {after}")

        if apply:
            session.commit()
            logger.info("Applied")
        else:
            session.rollback()
            logger.info("Dry run, nothing changed. Re-run with --apply")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Apply a reviewed location containment proposal"
    )
    parser.add_argument("path", help="CSV from propose_location_containment")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit the changes (default: dry run)",
    )

    args = parser.parse_args()
    try:
        apply_location_containment(args.path, apply=args.apply)
    except InvalidProposal as e:
        for error in e.errors:
            logger.error(error)
        logger.error(f"{e}; nothing was changed")
        sys.exit(1)
