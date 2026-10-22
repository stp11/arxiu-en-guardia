import os

import pytest
from sqlalchemy import inspect

from commands.restore_backup import restore
from database import engine


class TestRestore:
    # psql opens its own connection, so the table is created for real.
    @pytest.fixture(autouse=True)
    def drop_probe(self):
        yield
        with engine.begin() as conn:
            conn.exec_driver_sql("DROP TABLE IF EXISTS restore_probe")

    def restore(self, sql: str):
        restore(sql.encode(), os.environ["DATABASE_URL"])

    def probe_exists(self) -> bool:
        return inspect(engine).has_table("restore_probe")

    def test_restores_the_dump(self):
        self.restore("CREATE TABLE restore_probe (id int);")

        assert self.probe_exists()

    def test_restores_nothing_if_a_statement_fails(self):
        with pytest.raises(SystemExit):
            self.restore(
                "CREATE TABLE restore_probe (id int);\n"
                "INSERT INTO missing VALUES (1);\n"
            )

        assert not self.probe_exists()
