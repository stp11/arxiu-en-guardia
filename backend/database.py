import os

from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, create_engine

DATABASE_URL = os.environ["DATABASE_URL"]

is_debug = os.environ.get("BUILD_ENVIRONMENT") == "local"

engine = create_engine(DATABASE_URL, echo=is_debug, hide_parameters=True)

SessionLocal = sessionmaker(autocommit=False, bind=engine, class_=Session)


def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
