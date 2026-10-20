import csv
import json
import re
from types import SimpleNamespace

from sqlalchemy import func, text
from sqlmodel import Session, select

from commands.propose_category_merges import (
    CategoryInfo,
    Decision,
    co_occurring,
    nearest_names,
    propose_category_merges,
    resolve,
    to_decision,
)
from models import Category, CategoryType, Episode, EpisodeCategory


class FakeOpenAI:
    """Embeds names from a fixed table and reviews with canned decisions."""

    def __init__(self, vectors: dict[str, list[float]], decisions: dict):
        self.vectors = vectors
        self.decisions = decisions
        self.prompts = []
        self.embeddings = SimpleNamespace(create=self._embed)
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._review)
        )

    def _embed(self, input, model):
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=self.vectors[t]) for t in input]
        )

    def _review(self, messages, **kwargs):
        prompt = messages[0]["content"]
        self.prompts.append(prompt)
        # Categories under review start a line; their candidates are bullets.
        ids = [int(id) for id in re.findall(r"^\[(\d+)\]", prompt, re.M)]
        decisions = [
            {**keep(id), **self.decisions.get(id, {}), "id": id} for id in ids
        ]
        content = json.dumps({"decisions": decisions})
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


def keep(id: int) -> dict:
    return {
        "id": id,
        "action": "keep",
        "target_id": None,
        "new_name": None,
        "new_type": None,
        "reason": "Vàlida",
    }


def info(id: int, name: str, episodes: int = 1) -> CategoryInfo:
    return CategoryInfo(
        id, name, CategoryType.TOPIC, episode_ids=set(range(episodes))
    )


class TestProposeCategoryMerges:
    def setup_method(self):
        self.episodes = [
            Episode(id=1, title="Els ducats d'Atenes i Neopàtria"),
            Episode(id=2, title="La Corona al segle XIV"),
            Episode(id=3, title="La Guerra de Successió"),
            Episode(id=4, title="Almansa, 1707"),
            Episode(id=5, title="Felip V i la Nova Planta"),
            Episode(id=6, title="Les Corts de Montsó"),
        ]
        self.categories = {
            name: Category(name=name, slug=Category.slugify_name(name), type=t)
            for name, t in [
                ("Pere el Cerimoniós", CategoryType.CHARACTER),
                ("Pere III el Cerimoniós", CategoryType.CHARACTER),
                ("Prim Bertran", CategoryType.CHARACTER),
                ("Guerra de Successió", CategoryType.TOPIC),
                ("Batalla d'Almansa", CategoryType.TOPIC),
                ("Orfe", CategoryType.TOPIC),
            ]
        }
        self.links = {
            "Pere el Cerimoniós": [1, 2, 6],
            "Pere III el Cerimoniós": [1],
            "Prim Bertran": [2],
            "Guerra de Successió": [3, 4, 5],
            "Batalla d'Almansa": [4],
        }
        self.vectors = {
            "personatges: Pere el Cerimoniós": [1.0, 0.0, 0.0],
            "personatges: Pere III el Cerimoniós": [0.98, 0.1, 0.0],
            "personatges: Prim Bertran": [0.0, 1.0, 0.0],
            "temàtica: Guerra de Successió": [0.0, 0.0, 1.0],
            "temàtica: Batalla d'Almansa": [0.0, 0.3, 0.9],
        }

    def seed(self, db_session: Session) -> dict[str, int]:
        db_session.add_all(self.episodes)
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

    def run(self, db_session, monkeypatch, tmp_path, decisions) -> dict:
        fake = FakeOpenAI(self.vectors, decisions)
        monkeypatch.setattr(
            "commands.propose_category_merges.OpenAI", lambda api_key: fake
        )
        monkeypatch.setattr(
            "commands.propose_category_merges.get_session",
            lambda: iter([db_session]),
        )
        output = tmp_path / "merges.csv"

        propose_category_merges(str(output), batch_size=2, workers=1)

        self.prompts = fake.prompts
        with open(output, encoding="utf-8-sig") as file:
            return {row["name"]: row for row in csv.DictReader(file)}

    def test_writes_reviewed_proposal(self, db_session, monkeypatch, tmp_path):
        ids = self.seed(db_session)

        rows = self.run(
            db_session,
            monkeypatch,
            tmp_path,
            {
                ids["Pere III el Cerimoniós"]: {
                    "action": "merge",
                    "target_id": ids["Pere el Cerimoniós"],
                },
                ids["Prim Bertran"]: {"action": "delete"},
                ids["Batalla d'Almansa"]: {
                    "action": "rollup",
                    "target_id": ids["Guerra de Successió"],
                },
            },
        )

        merged = rows["Pere III el Cerimoniós"]
        assert merged["action"] == "merge"
        assert merged["target_name"] == "Pere el Cerimoniós"
        assert merged["target_type"] == "character"
        assert rows["Prim Bertran"]["action"] == "delete"
        assert rows["Batalla d'Almansa"]["action"] == "rollup"
        assert rows["Pere el Cerimoniós"]["action"] == "keep"
        assert rows["Pere el Cerimoniós"]["episodes"] == "3"
        assert rows["Orfe"]["action"] == "delete"
        assert rows["Orfe"]["reason"] == "Sense episodis"
        assert "Orfe" not in "".join(self.prompts)

    def test_offers_well_used_topics_and_locations_as_general(
        self, db_session, monkeypatch, tmp_path
    ):
        ids = self.seed(db_session)

        self.run(db_session, monkeypatch, tmp_path, {})

        prompt = self.prompts[0]
        general = prompt.split("# CATEGORIES GENERALS")[1].split("# CATEG")[0]
        war, king = ids["Guerra de Successió"], ids["Pere el Cerimoniós"]
        assert f"- [{war}]" in general
        assert f"- [{king}]" not in general

    def test_leaves_the_database_untouched(
        self, db_session, monkeypatch, tmp_path
    ):
        ids = self.seed(db_session)

        self.run(
            db_session,
            monkeypatch,
            tmp_path,
            {ids["Prim Bertran"]: {"action": "delete"}},
        )

        categories = db_session.exec(select(Category)).all()
        assert len(categories) == len(self.categories)
        links = db_session.exec(select(func.count(EpisodeCategory.episode_id)))
        assert links.one() == sum(len(ids) for ids in self.links.values())
        temp_table = db_session.connection().execute(
            text("SELECT to_regclass('pg_temp.category_name_embedding')")
        )
        assert temp_table.scalar() is None


class TestNearestNames:
    def test_ranks_neighbours_by_embedding_distance(self, db_session):
        embeddings = {1: [1.0, 0.0], 2: [0.9, 0.1], 3: [0.0, 1.0]}

        result = nearest_names(db_session, embeddings, limit=1)

        assert result == {1: [2], 2: [1], 3: [2]}


class TestCoOccurring:
    def test_ranks_by_shared_episodes_then_size(self):
        categories = {
            1: CategoryInfo(1, "Batalla", None, {10, 11}),
            2: CategoryInfo(2, "Guerra", None, {10, 11, 12, 13}),
            3: CategoryInfo(3, "Rei", None, {10, 20}),
            4: CategoryInfo(4, "Ciutat", None, {11}),
        }

        result = co_occurring(categories)

        assert result[1] == [2, 3, 4]


class TestToDecision:
    def test_keeps_when_target_is_not_a_candidate(self):
        raw = {**keep(1), "action": "merge", "target_id": 99}

        decision = to_decision(info(1, "Guerra"), raw, allowed_targets={2})

        assert decision.action == "keep"
        assert decision.target_id is None

    def test_keeps_when_targeting_itself(self):
        raw = {**keep(1), "action": "rollup", "target_id": 1}

        decision = to_decision(info(1, "Guerra"), raw, allowed_targets={1})

        assert decision.action == "keep"

    def test_keeps_when_the_review_failed(self):
        decision = to_decision(info(1, "Guerra"), None, allowed_targets={2})

        assert decision.action == "keep"

    def test_drops_renames_to_the_same_name_and_type(self):
        raw = {**keep(1), "new_name": "Guerra", "new_type": "temàtica"}

        decision = to_decision(info(1, "Guerra"), raw, allowed_targets=set())

        assert decision.new_name is None
        assert decision.new_type is None


class TestResolve:
    def test_follows_merge_chains_to_the_survivor(self):
        categories = {i: info(i, f"C{i}") for i in (1, 2, 3)}
        decisions = {
            1: Decision("merge", "", target_id=2),
            2: Decision("merge", "", target_id=3),
            3: Decision("keep", ""),
        }

        resolve(decisions, categories)

        assert decisions[1].target_id == 3
        assert decisions[2].target_id == 3

    def test_rolls_up_past_merged_categories(self):
        categories = {i: info(i, f"C{i}") for i in (1, 2, 3, 4)}
        decisions = {
            1: Decision("rollup", "", target_id=2),
            2: Decision("merge", "", target_id=3),
            3: Decision("keep", ""),
            4: Decision("merge", "", target_id=1),
        }

        resolve(decisions, categories)

        assert decisions[1].target_id == 3
        # A rolled-up category survives, so merges into it stay put.
        assert decisions[4].target_id == 1

    def test_keeps_categories_rolling_up_into_one_that_goes_away(self):
        categories = {i: info(i, f"C{i}") for i in (1, 2, 3, 4)}
        decisions = {
            1: Decision("rollup", "", target_id=2),
            2: Decision("delete", ""),
            3: Decision("rollup", "", target_id=4),
            4: Decision("merge", "", target_id=3),
        }

        resolve(decisions, categories)

        assert decisions[1].action == "keep"
        assert decisions[3].action == "keep"

    def test_breaks_a_rollup_ring(self):
        categories = {i: info(i, f"C{i}") for i in (1, 2)}
        decisions = {
            1: Decision("rollup", "", target_id=2),
            2: Decision("rollup", "", target_id=1),
        }

        resolve(decisions, categories)

        assert decisions[1].action == "keep"
        assert decisions[2].target_id == 1

    def test_breaks_a_merge_ring_at_its_biggest_category(self):
        categories = {1: info(1, "Gran", episodes=5), 2: info(2, "Petita")}
        decisions = {
            1: Decision("merge", "", target_id=2),
            2: Decision("merge", "", target_id=1),
        }

        resolve(decisions, categories)

        assert decisions[1].action == "keep"
        assert decisions[2].target_id == 1

    def test_keeps_categories_merging_into_a_deleted_one(self):
        categories = {i: info(i, f"C{i}") for i in (1, 2)}
        decisions = {
            1: Decision("merge", "", target_id=2),
            2: Decision("delete", ""),
        }

        resolve(decisions, categories)

        assert decisions[1].action == "keep"

    def test_turns_a_rename_onto_an_existing_name_into_a_merge(self):
        categories = {1: info(1, "Pere III"), 2: info(2, "Pere el Gran")}
        decisions = {
            1: Decision("keep", "", new_name="Pere el Gran"),
            2: Decision("keep", ""),
        }

        resolve(decisions, categories)

        assert decisions[1].action == "merge"
        assert decisions[1].target_id == 2
