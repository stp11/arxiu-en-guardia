import os

from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, create_engine

DATABASE_URL = os.environ["DATABASE_URL"]

# SQLAlchemy 2.1 maps a bare postgresql:// URL to psycopg 3; we ship psycopg2.
# The env var keeps the bare scheme because pg_dump/psql also consume it.
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://", "postgresql+psycopg2://", 1
    )

is_debug = os.environ.get("BUILD_ENVIRONMENT") == "local"

engine = create_engine(DATABASE_URL, echo=is_debug, hide_parameters=True)

SessionLocal = sessionmaker(autocommit=False, bind=engine, class_=Session)


def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
