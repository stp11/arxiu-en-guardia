from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlmodel import Session

from alembic import command
from alembic.config import Config
from database import DATABASE_URL, engine, get_session
from main import app

# Tests commit and roll back freely, so never point them at real data.
if not (make_url(DATABASE_URL).database or "").endswith("_test"):
    pytest.exit(
        "DATABASE_URL must point to a dedicated Postgres database whose "
        "name ends in '_test'",
        returncode=1,
    )


@pytest.fixture(scope="session", autouse=True)
def migrate_test_db():
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).parent.parent / "alembic")
    )
    command.upgrade(config, "head")


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session):
    def get_session_override():
        yield db_session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
