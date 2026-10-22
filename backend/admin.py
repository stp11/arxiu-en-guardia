from fastapi import Request
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import engine
from models import Users


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

            if user and user.verify_password(password):
                if user.password_needs_rehash():
                    user.password_hash = Users.hash_password(password)
                    session.commit()
                request.session.update(
                    {"user_id": user.id, "user_username": user.username}
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
            return user is not None
