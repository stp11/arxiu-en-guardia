import csv

import pytest
from sqlmodel import Session, select

from commands.apply_category_merges import (
    InvalidProposal,
    apply_category_merges,
)
from commands.propose_category_merges import CSV_FIELDS
from models import Category, CategoryType, Episode, EpisodeCategory


class TestApplyCategoryMerges:
    def setup_method(self):
        self.categories = {
            name: Category(name=name, slug=Category.slugify_name(name), type=t)
            for name, t in [
                ("Pere el Cerimoniós", CategoryType.CHARACTER),
                ("Pere III el Cerimoniós", CategoryType.CHARACTER),
                ("Guerra de Successió", CategoryType.TOPIC),
                ("Batalla d'Almansa", CategoryType.TOPIC),
                ("Prim Bertran", CategoryType.CHARACTER),
                ("Boleros", None),
                ("comte-duc d'Olivares", CategoryType.CHARACTER),
                ("Barcelona", CategoryType.LOCATION),
            ]
        }
        self.links = {
            "Pere el Cerimoniós": [1, 2],
            "Pere III el Cerimoniós": [1, 3],
            "Guerra de Successió": [3],
            "Batalla d'Almansa": [4],
            "Prim Bertran": [2],
            "Boleros": [4],
            "comte-duc d'Olivares": [3],
            "Barcelona": [1],
        }

    def seed(self, db_session: Session) -> dict[str, int]:
        db_session.add_all(
            Episode(id=id, title=f"Episodi {id}") for id in range(1, 5)
        )
        db_session.add_all(self.categories.values())
        db_session.flush()
        for name, episode_ids in self.links.items():
            for episode_id in episode_ids:
                db_session.add(
                    EpisodeCategory(
                        episode_id=episode_id,
                        category_id=self.categories[name].id,
                    )
                )
        db_session.commit()
        return {name: c.id for name, c in self.categories.items()}

    def write(self, tmp_path, ids, rows, delimiter=","):
        path = tmp_path / "merges.csv"
        with open(path, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(
                file, fieldnames=CSV_FIELDS, delimiter=delimiter, restval=""
            )
            writer.writeheader()
            for name, fields in rows.items():
                writer.writerow({"id": ids[name], "name": name, **fields})
        return str(path)

    def run(self, db_session, monkeypatch, path, apply=True):
        monkeypatch.setattr(
            "commands.apply_category_merges.get_session",
            lambda: iter([db_session]),
        )
        apply_category_merges(path, apply=apply)

    def episodes_of(self, db_session) -> dict[str, set[int]]:
        result = {}
        for category in db_session.exec(select(Category)):
            links = db_session.exec(
                select(EpisodeCategory.episode_id).where(
                    EpisodeCategory.category_id == category.id
                )
            )
            result[category.name] = set(links)
        return result

    def reviewed(self, ids) -> dict:
        return {
            "Pere el Cerimoniós": {"action": "keep"},
            "Pere III el Cerimoniós": {
                "action": "merge",
                "target_id": ids["Pere el Cerimoniós"],
            },
            "Batalla d'Almansa": {
                "action": "rollup",
                "target_id": ids["Guerra de Successió"],
            },
            "Prim Bertran": {"action": "delete"},
            "Boleros": {"action": "keep", "new_type": "topic"},
            "comte-duc d'Olivares": {
                "action": "keep",
                "new_name": "Comte-duc d'Olivares",
            },
        }

    def test_applies_the_reviewed_actions(
        self, db_session, monkeypatch, tmp_path
    ):
        ids = self.seed(db_session)
        path = self.write(tmp_path, ids, self.reviewed(ids))

        self.run(db_session, monkeypatch, path)

        assert self.episodes_of(db_session) == {
            "Pere el Cerimoniós": {1, 2, 3},
            "Guerra de Successió": {3, 4},
            "Batalla d'Almansa": {4},
            "Boleros": {4},
            "Comte-duc d'Olivares": {3},
            "Barcelona": {1},
        }
        boleros = db_session.get(Category, ids["Boleros"])
        assert boleros.type == CategoryType.TOPIC
        olivares = db_session.get(Category, ids["comte-duc d'Olivares"])
        assert olivares.slug == "comte-duc-d-olivares"

    def test_dry_run_changes_nothing(self, db_session, monkeypatch, tmp_path):
        ids = self.seed(db_session)
        before = self.episodes_of(db_session)
        path = self.write(tmp_path, ids, self.reviewed(ids))

        self.run(db_session, monkeypatch, path, apply=False)

        assert self.episodes_of(db_session) == before
        assert db_session.get(Category, ids["Boleros"]).type is None

    def test_follows_merges_chained_by_hand(
        self, db_session, monkeypatch, tmp_path
    ):
        ids = self.seed(db_session)
        rows = {
            "Pere III el Cerimoniós": {
                "action": "merge",
                "target_id": ids["Pere el Cerimoniós"],
            },
            "Pere el Cerimoniós": {
                "action": "merge",
                "target_id": ids["Barcelona"],
            },
        }
        path = self.write(tmp_path, ids, rows)

        self.run(db_session, monkeypatch, path)

        assert self.episodes_of(db_session)["Barcelona"] == {1, 2, 3}

    def test_rollups_tag_every_broader_category_up_the_chain(
        self, db_session, monkeypatch, tmp_path
    ):
        ids = self.seed(db_session)
        # The broader rollup comes first, so its own episodes are copied
        # before the narrower rollup adds to them.
        rows = {
            "Guerra de Successió": {
                "action": "rollup",
                "target_id": ids["Barcelona"],
            },
            "Batalla d'Almansa": {
                "action": "rollup",
                "target_id": ids["Guerra de Successió"],
            },
            "Prim Bertran": {
                "action": "merge",
                "target_id": ids["Batalla d'Almansa"],
            },
        }
        path = self.write(tmp_path, ids, rows)

        self.run(db_session, monkeypatch, path)

        episodes = self.episodes_of(db_session)
        assert episodes["Batalla d'Almansa"] == {2, 4}
        assert episodes["Guerra de Successió"] == {2, 3, 4}
        assert episodes["Barcelona"] == {1, 2, 3, 4}
        assert "Prim Bertran" not in episodes

    def test_rename_can_take_a_name_freed_by_a_merge(
        self, db_session, monkeypatch, tmp_path
    ):
        ids = self.seed(db_session)
        rows = {
            "Pere III el Cerimoniós": {
                "action": "merge",
                "target_id": ids["Pere el Cerimoniós"],
            },
            "comte-duc d'Olivares": {
                "action": "keep",
                "new_name": "Pere III el Cerimoniós",
            },
        }
        path = self.write(tmp_path, ids, rows)

        self.run(db_session, monkeypatch, path)

        renamed = db_session.get(Category, ids["comte-duc d'Olivares"])
        assert renamed.slug == "pere-iii-el-cerimonios"

    def test_reads_semicolon_separated_files(
        self, db_session, monkeypatch, tmp_path
    ):
        ids = self.seed(db_session)
        rows = {"Prim Bertran": {"action": "delete"}}
        path = self.write(tmp_path, ids, rows, delimiter=";")

        self.run(db_session, monkeypatch, path)

        assert "Prim Bertran" not in self.episodes_of(db_session)

    def test_reads_quotes_inside_fields(
        self, db_session, monkeypatch, tmp_path
    ):
        ids = self.seed(db_session)
        rows = {
            "Boleros": {
                "action": "keep",
                "new_name": 'Boleros "de Cuba"',
                "reason": 'Diu "boleros"; és música',
            }
        }
        path = self.write(tmp_path, ids, rows, delimiter=";")

        self.run(db_session, monkeypatch, path)

        boleros = db_session.get(Category, ids["Boleros"])
        assert boleros.name == 'Boleros "de Cuba"'

    def test_rejects_unreadable_rows(self, db_session, monkeypatch, tmp_path):
        ids = self.seed(db_session)
        rows = {
            "Prim Bertran": {"action": "esborrar"},
            "Pere III el Cerimoniós": {"action": "merge"},
            "Boleros": {"action": "keep", "new_type": "música"},
        }
        path = self.write(tmp_path, ids, rows)

        with pytest.raises(InvalidProposal) as raised:
            self.run(db_session, monkeypatch, path)

        assert len(raised.value.errors) == 3

    def test_rejects_inconsistent_rows_without_changing_anything(
        self, db_session, monkeypatch, tmp_path
    ):
        ids = self.seed(db_session)
        before = self.episodes_of(db_session)
        rows = {
            "Prim Bertran": {"action": "delete"},
            "Pere III el Cerimoniós": {
                "action": "merge",
                "target_id": ids["Prim Bertran"],
            },
            "Batalla d'Almansa": {
                "action": "rollup",
                "target_id": ids["Batalla d'Almansa"],
            },
            "Boleros": {"action": "keep", "new_name": "Barcelona"},
            "Guerra de Successió": {"action": "keep"},
        }
        path = self.write(tmp_path, ids, rows)
        db_session.get(Category, ids["Guerra de Successió"]).name = "Altre"
        db_session.commit()

        with pytest.raises(InvalidProposal) as raised:
            self.run(db_session, monkeypatch, path)

        errors = "\n".join(raised.value.errors)
        assert "is being deleted" in errors
        assert "loop back" in errors
        assert "clashes with" in errors
        assert "is named 'Altre' now" in errors
        before["Altre"] = before.pop("Guerra de Successió")
        assert self.episodes_of(db_session) == before
