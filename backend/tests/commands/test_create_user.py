from sqlmodel import Session

from commands.create_user import set_password
from models import Users


class TestSetPassword:
    def test_replaces_the_password(self, db_session: Session, monkeypatch):
        monkeypatch.setattr(
            "commands.create_user.engine", db_session.connection()
        )
        user = Users(username="admin", password_hash=Users.hash_password("pa"))
        db_session.add(user)
        db_session.commit()

        assert set_password("admin", "pb")

        db_session.refresh(user)
        assert user.verify_password("pb")
        assert not user.verify_password("pa")

    def test_refuses_an_unknown_user(self, db_session: Session, monkeypatch):
        monkeypatch.setattr(
            "commands.create_user.engine", db_session.connection()
        )

        assert not set_password("ningú", "pb")
