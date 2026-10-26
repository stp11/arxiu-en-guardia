import hashlib
import hmac

from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import engine
from models import Users


def password_fingerprint(user: Users) -> str:
    """Ties a session to the password it was opened with, so changing the
    password ends it. The cookie is signed but readable, hence a digest."""
    return hashlib.sha256(user.password_hash.encode()).hexdigest()[:16]


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")

        if not username or not password:
            return False

        with Session(bind=engine) as session:
            statement = select(Users).where(
                Users.username == username,
                Users.is_active.is_(True),
            )
            user = session.execute(statement).scalars().first()

            if user and await run_in_threadpool(
                user.verify_password, password
            ):
                if user.password_needs_rehash():
                    user.password_hash = await run_in_threadpool(
                        Users.hash_password, password
                    )
                    session.commit()
                request.session.update(
                    {
                        "user_id": user.id,
                        "user_username": user.username,
                        "password": password_fingerprint(user),
                    }
                )
                return True

        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        user_id = request.session.get("user_id")

        if not user_id:
            return False

        with Session(bind=engine) as session:
            statement = select(Users).where(
                Users.id == user_id, Users.is_active.is_(True)
            )
            user = session.execute(statement).scalars().first()
            return user is not None and hmac.compare_digest(
                request.session.get("password", ""),
                password_fingerprint(user),
            )
