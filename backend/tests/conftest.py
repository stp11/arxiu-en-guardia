import os
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlmodel import Session

from alembic import command
from alembic.config import Config


def with_database(url: str, name: str) -> str:
    # Swap only the path so credentials and query params stay byte-for-byte.
    return urlsplit(url)._replace(path=f"/{name}").geturl()


# Each run creates, migrates and drops its own database on the DATABASE_URL
# server; the configured database is never connected to. This has to happen
# before the app imports `database`, which builds its engine from the env var.
# A hard-killed run can leave an en_guardia_test_* behind; it's safe to drop.
SERVER_URL = os.environ["DATABASE_URL"]
TEST_DB_NAME = f"en_guardia_test_{uuid4().hex[:12]}"
os.environ["DATABASE_URL"] = with_database(SERVER_URL, TEST_DB_NAME)

from database import engine, get_session  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture(scope="session")
def alembic_config():
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).parent.parent / "alembic")
    )
    return config


@pytest.fixture(scope="session", autouse=True)
def disposable_db(alembic_config):
    admin = create_engine(
        with_database(SERVER_URL, "postgres"), isolation_level="AUTOCOMMIT"
    )
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    try:
        command.upgrade(alembic_config, "head")
        yield
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE "{TEST_DB_NAME}" WITH (FORCE)'))
        admin.dispose()


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
