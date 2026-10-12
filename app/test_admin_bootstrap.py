from uuid import UUID, uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.admin_bootstrap import bootstrap_admin
from app.database import Base
from app.models import UserProfile


class FakeSupabaseAdmin:
    def __init__(self, existing=None):
        self.user = existing
        self.create_calls = 0

    def find_user_by_email(self, email):
        if self.user and self.user["email"].casefold() == email.casefold():
            return self.user
        return None

    def create_user(self, email, password):
        self.create_calls += 1
        assert password
        self.user = {"id": str(uuid4()), "email": email}
        return self.user


def test_bootstrap_promotes_existing_user_without_password_reset():
    user = {"id": str(uuid4()), "email": "admin@example.test"}
    client = FakeSupabaseAdmin(existing=user)
    engine = create_engine("sqlite://")
    UserProfile.__table__.create(engine)
    try:
        with Session(engine) as db:
            result = bootstrap_admin(client, db, user["email"], "")
            profile = db.get(UserProfile, result)
        assert result == UUID(str(user["id"]))
        assert client.create_calls == 0
        assert profile.role == "admin"
        assert profile.is_active is True
    finally:
        engine.dispose()


def test_bootstrap_creates_once_and_is_idempotent():
    client = FakeSupabaseAdmin()
    engine = create_engine("sqlite://")
    UserProfile.__table__.create(engine)
    try:
        with Session(engine) as db:
            first_id = bootstrap_admin(
                client,
                db,
                "admin@example.test",
                "provided-only-to-the-bootstrap-call",
            )
            second_id = bootstrap_admin(
                client,
                db,
                "admin@example.test",
                "new-password-must-not-be-used",
            )
        assert first_id == second_id
        assert client.create_calls == 1
    finally:
        engine.dispose()
