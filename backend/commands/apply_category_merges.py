"""
Apply a reviewed category consolidation from propose_category_merges.

Checks the CSV against the database, then merges, rolls up, deletes,
renames and retypes categories in a single transaction. A rollup keeps
its category and also tags its episodes with the broader one. Without
--apply everything is rolled back and only the outcome is reported.

Only the columns that matter for each row's action are read: target_id
for merge and rollup, new_name and new_type for keep. Categories missing
from the CSV are left alone.

Usage:
    python -m commands.apply_category_merges category_merges.csv
    python -m commands.apply_category_merges category_merges.csv --apply
"""

import csv
import sys
from dataclasses import dataclass, field

from sqlalchemy import delete, func, literal
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, select

from commands.propose_category_merges import TARGET_ACTIONS
from database import get_session
from logger import logger
from models import Category, CategoryType, EpisodeCategory
from prompts import CATEGORY_REVIEW_ACTIONS

REQUIRED_COLUMNS = {
    "id",
    "name",
    "action",
    "target_id",
    "new_name",
    "new_type",
}


class InvalidProposal(Exception):
    def __init__(self, errors: list[str]):
        super().__init__(f"{len(errors)} problems in the proposal")
        self.errors = errors


@dataclass
class Row:
    line: int
    id: int
    name: str
    action: str
    target_id: int | None = None
    new_name: str | None = None
    new_type: CategoryType | None = None


@dataclass
class Plan:
    merges: dict[int, int] = field(default_factory=dict)
    rollups: dict[int, list[int]] = field(default_factory=dict)
    deletes: list[int] = field(default_factory=list)
    renames: dict[int, str] = field(default_factory=dict)
    retypes: dict[int, CategoryType] = field(default_factory=dict)


def read_rows(path: str) -> list[Row]:
    with open(path, newline="", encoding="utf-8-sig") as file:
        # Spreadsheets in a Catalan or Spanish locale save with semicolons.
        # Only the delimiter is sniffed: from a header without quotes the
        # sniffer would also turn off reading "" as an escaped quote.
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
                rows.append(_parse_row(line, raw))
            except ValueError as e:
                errors.append(f"Line {line}: {e}")

    if errors:
        raise InvalidProposal(errors)
    return rows


def _parse_row(line: int, raw: dict) -> Row:
    action = raw["action"].strip().lower()
    if action not in CATEGORY_REVIEW_ACTIONS:
        raise ValueError(f"unknown action {raw['action']!r}")
    row = Row(line, _parse_id(raw["id"], "id"), raw["name"], action)

    if action in TARGET_ACTIONS:
        if not raw["target_id"].strip():
            raise ValueError(f"{action} needs a target_id")
        row.target_id = _parse_id(raw["target_id"], "target_id")
    elif action == "keep":
        row.new_name = raw["new_name"].strip() or None
        new_type = raw["new_type"].strip()
        if new_type:
            try:
                row.new_type = CategoryType(new_type)
            except ValueError:
                types = ", ".join(type.value for type in CategoryType)
                raise ValueError(
                    f"unknown new_type {new_type!r} (use one of: {types})"
                )
    return row


def _parse_id(value: str, column: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{column} {value!r} is not a number")


def build_plan(session: Session, rows: list[Row]) -> Plan:
    categories = {c.id: c for c in session.exec(select(Category))}
    errors = []
    by_id: dict[int, Row] = {}
    for row in rows:
        category = categories.get(row.id)
        if row.id in by_id:
            errors.append(f"Line {row.line}: category {row.id} is repeated")
        elif category is None:
            errors.append(
                f"Line {row.line}: category {row.id} no longer exists"
            )
        elif category.name != row.name:
            errors.append(
                f"Line {row.line}: category {row.id} is named "
                f"{category.name!r} now, not {row.name!r}; "
                "use new_name to rename it"
            )
        else:
            by_id[row.id] = row

    plan = Plan()
    for row in by_id.values():
        if row.action in TARGET_ACTIONS:
            try:
                if row.action == "merge":
                    plan.merges[row.id] = _survivor(
                        row.id, row.target_id, by_id, categories
                    )
                else:
                    plan.rollups[row.id] = _broader(row, by_id, categories)
            except ValueError as e:
                errors.append(f"Line {row.line}: {e}")
        elif row.action == "delete":
            plan.deletes.append(row.id)
        else:
            if row.new_name and row.new_name != categories[row.id].name:
                plan.renames[row.id] = row.new_name
            if row.new_type and row.new_type != categories[row.id].type:
                plan.retypes[row.id] = row.new_type

    errors += _slug_clashes(plan, by_id, categories)
    if errors:
        raise InvalidProposal(errors)
    return plan


def _survivor(
    id: int,
    target: int,
    by_id: dict[int, Row],
    categories: dict[int, Category],
) -> int:
    # Merges can chain once rows are edited by hand; follow them through.
    path = [id]
    while target in by_id and by_id[target].action == "merge":
        if target in path:
            raise ValueError(f"merges loop back to category {target}")
        path.append(target)
        target = by_id[target].target_id

    if target not in categories:
        raise ValueError(f"target {target} does not exist")
    if target in by_id and by_id[target].action == "delete":
        raise ValueError(
            f"target {target} ({categories[target].name!r}) is being deleted"
        )
    return target


def _broader(
    row: Row, by_id: dict[int, Row], categories: dict[int, Category]
) -> list[int]:
    # Every category up the chain, so a district also gets its city's
    # region, whichever order the rollups run in.
    chain = []
    current, target = row.id, row.target_id
    while True:
        target = _survivor(current, target, by_id, categories)
        if target == row.id or target in chain:
            raise ValueError(f"rollups loop back to category {target}")
        chain.append(target)
        if target not in by_id or by_id[target].action != "rollup":
            return chain
        current, target = target, by_id[target].target_id


def _slug_clashes(
    plan: Plan, by_id: dict[int, Row], categories: dict[int, Category]
) -> list[str]:
    gone = {*plan.merges, *plan.deletes}
    owners = {
        category.slug: id
        for id, category in categories.items()
        if id not in gone and id not in plan.renames
    }
    errors = []
    for id, name in plan.renames.items():
        slug = Category.slugify_name(name)
        owner = owners.setdefault(slug, id)
        if owner != id:
            errors.append(
                f"Line {by_id[id].line}: new name {name!r} clashes with "
                f"category {owner} ({categories[owner].name!r}); "
                "merge into it instead"
            )
    return errors


def apply_plan(session: Session, plan: Plan) -> None:
    for source, target in plan.merges.items():
        _copy_links(session, source, target)
    # After the merges, so a rollup carries the episodes merged into it.
    for source, targets in plan.rollups.items():
        for target in targets:
            _copy_links(session, source, target)

    for id in [*plan.merges, *plan.deletes]:
        session.exec(
            delete(EpisodeCategory).where(EpisodeCategory.category_id == id)
        )
        session.exec(delete(Category).where(Category.id == id))

    # After the deletes, so a rename can take a slug that was just freed.
    for id, name in plan.renames.items():
        category = session.get(Category, id)
        category.name = name
        category.slug = Category.slugify_name(name)
    for id, type in plan.retypes.items():
        session.get(Category, id).type = type
    session.flush()


def _copy_links(session: Session, source: int, target: int) -> None:
    episodes = select(EpisodeCategory.episode_id, literal(target)).where(
        EpisodeCategory.category_id == source
    )
    session.exec(
        insert(EpisodeCategory)
        .from_select(["episode_id", "category_id"], episodes)
        .on_conflict_do_nothing()
    )


def _counts(session: Session) -> tuple[int, int]:
    categories = session.exec(select(func.count(Category.id))).one()
    links = session.exec(select(func.count(EpisodeCategory.episode_id))).one()
    return categories, links


def apply_category_merges(path: str, apply: bool = False) -> None:
    rows = read_rows(path)

    with next(get_session()) as session:
        plan = build_plan(session, rows)
        categories_before, links_before = _counts(session)
        apply_plan(session, plan)
        categories_after, links_after = _counts(session)

        logger.info(
            f"Merged {len(plan.merges)}, rolled up "
            f"{len(plan.rollups)}, deleted {len(plan.deletes)}, renamed "
            f"{len(plan.renames)}, retyped {len(plan.retypes)}"
        )
        logger.info(
            f"Categories: {categories_before} -> {categories_after}. "
            f"Episode links: {links_before} -> {links_after}"
        )

        if apply:
            session.commit()
            logger.info("Applied")
        else:
            session.rollback()
            logger.info("Dry run, nothing changed. Re-run with --apply")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Apply a reviewed category merge proposal"
    )
    parser.add_argument("path", help="CSV from propose_category_merges")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit the changes (default: dry run)",
    )

    args = parser.parse_args()
    try:
        apply_category_merges(args.path, apply=args.apply)
    except InvalidProposal as e:
        for error in e.errors:
            logger.error(error)
        logger.error(f"{e}; nothing was changed")
        sys.exit(1)
