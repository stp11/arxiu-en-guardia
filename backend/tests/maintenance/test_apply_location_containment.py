import csv

import pytest
from sqlmodel import select

from maintenance.apply_location_containment import (
    InvalidProposal,
    apply_location_containment,
)
from maintenance.propose_location_containment import CSV_FIELDS
from models import Category, CategoryType, Episode, EpisodeCategory


class TestApplyLocationContainment:
    TAGS = {
        1: ["Europa", "França", "París"],
        2: ["Barcelona", "Raval"],
        3: ["Europa"],
    }

    def seed(self, db_session) -> dict[str, int]:
        names = sorted({name for tags in self.TAGS.values() for name in tags})
        categories = {
            name: Category(
                name=name,
                slug=Category.slugify_name(name),
                type=CategoryType.LOCATION,
            )
            for name in names
        }
        db_session.add_all(
            Episode(id=id, title=f"Episodi {id}") for id in self.TAGS
        )
        db_session.add_all(categories.values())
        db_session.flush()
        for episode_id, tags in self.TAGS.items():
            for name in tags:
                db_session.add(
                    EpisodeCategory(
                        episode_id=episode_id,
                        category_id=categories[name].id,
                    )
                )
        db_session.commit()
        return {name: category.id for name, category in categories.items()}

    def write(self, tmp_path, ids, rows, delimiter=","):
        path = tmp_path / "containment.csv"
        with open(path, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(
                file, fieldnames=CSV_FIELDS, delimiter=delimiter
            )
            writer.writeheader()
            for episode_id, remove, because_of in rows:
                writer.writerow(
                    {
                        "episode_id": episode_id,
                        "episode": f"Episodi {episode_id}",
                        "remove_id": ids[remove],
                        "remove": remove,
                        "because_of_id": ids[because_of],
                        "because_of": because_of,
                        "path": "P17",
                    }
                )
        return str(path)

    def run(self, db_session, monkeypatch, path, apply=True):
        monkeypatch.setattr(
            "maintenance.apply_location_containment.get_session",
            lambda: iter([db_session]),
        )
        apply_location_containment(path, apply=apply)

    def tags(self, db_session) -> dict[int, set[str]]:
        rows = db_session.exec(
            select(EpisodeCategory.episode_id, Category.name).join(Category)
        )
        found = {}
        for episode_id, name in rows:
            found.setdefault(episode_id, set()).add(name)
        return found

    REVIEWED = [
        (1, "Europa", "París"),
        (1, "França", "París"),
        (2, "Barcelona", "Raval"),
    ]

    def test_removes_the_reviewed_locations(
        self, db_session, monkeypatch, tmp_path
    ):
        ids = self.seed(db_session)
        path = self.write(tmp_path, ids, self.REVIEWED)

        self.run(db_session, monkeypatch, path)

        assert self.tags(db_session) == {
            1: {"París"},
            2: {"Raval"},
            3: {"Europa"},
        }

    def test_dry_run_changes_nothing(self, db_session, monkeypatch, tmp_path):
        ids = self.seed(db_session)
        before = self.tags(db_session)
        path = self.write(tmp_path, ids, self.REVIEWED)

        self.run(db_session, monkeypatch, path, apply=False)

        assert self.tags(db_session) == before

    def test_reads_semicolons(self, db_session, monkeypatch, tmp_path):
        ids = self.seed(db_session)
        path = self.write(tmp_path, ids, self.REVIEWED[:1], delimiter=";")

        self.run(db_session, monkeypatch, path)

        assert self.tags(db_session)[1] == {"França", "París"}

    def expect_errors(self, db_session, monkeypatch, path, *messages):
        before = self.tags(db_session)
        with pytest.raises(InvalidProposal) as error:
            self.run(db_session, monkeypatch, path)
        assert len(error.value.errors) == len(messages)
        for found, message in zip(error.value.errors, messages):
            assert message in found
        assert self.tags(db_session) == before

    def test_refuses_leaving_a_removal_unexplained(
        self, db_session, monkeypatch, tmp_path
    ):
        ids = self.seed(db_session)
        # França explains Europa, but goes too.
        rows = [(1, "Europa", "França"), (1, "França", "París")]
        path = self.write(tmp_path, ids, rows)

        self.expect_errors(
            db_session,
            monkeypatch,
            path,
            "Line 2: 'França', which explains removing 'Europa'",
        )

    def test_refuses_what_changed_since_the_proposal(
        self, db_session, monkeypatch, tmp_path
    ):
        ids = self.seed(db_session)
        path = self.write(
            tmp_path,
            ids,
            [
                (3, "Europa", "París"),
                (1, "Europa", "París"),
                (4, "Barcelona", "Raval"),
            ],
        )
        db_session.get(Category, ids["París"]).name = "Paris"
        db_session.commit()

        self.expect_errors(
            db_session,
            monkeypatch,
            path,
            "Line 2: location",
            "Line 3: location",
            "Line 4: episode 4 no longer exists",
        )

    def test_refuses_a_location_the_episode_lacks(
        self, db_session, monkeypatch, tmp_path
    ):
        ids = self.seed(db_session)
        path = self.write(tmp_path, ids, [(3, "França", "Europa")])

        self.expect_errors(
            db_session,
            monkeypatch,
            path,
            "Line 2: episode 3 no longer has 'França'",
        )

    def test_refuses_repeated_rows(self, db_session, monkeypatch, tmp_path):
        ids = self.seed(db_session)
        rows = [(2, "Barcelona", "Raval"), (2, "Barcelona", "Raval")]
        path = self.write(tmp_path, ids, rows)

        self.expect_errors(
            db_session,
            monkeypatch,
            path,
            "Line 2: episode 2 loses 'Barcelona' twice",
        )
