from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth
from app.database import Base, get_db
from app.main import app
from app.models import InterviewSession, UserProfile


@pytest.fixture
def admin_api():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[UserProfile.__table__, InterviewSession.__table__],
    )
    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS auth")
        connection.exec_driver_sql(
            """
            CREATE TABLE auth.users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    admin = UserProfile(id=uuid4(), role="admin", is_active=True)
    regular = UserProfile(id=uuid4(), role="user", is_active=True)
    revoked = UserProfile(id=uuid4(), role="user", is_active=False)
    created_at = datetime.now(timezone.utc).isoformat()
    with factory() as db:
        db.add_all([admin, regular, revoked])
        db.commit()
        for profile, email in (
            (admin, "admin@example.test"),
            (regular, "candidate@example.test"),
            (revoked, "revoked@example.test"),
        ):
            db.execute(
                text(
                    "INSERT INTO auth.users (id, email, created_at) "
                    "VALUES (:id, :email, :created_at)"
                ),
                {
                    "id": profile.id.hex,
                    "email": email,
                    "created_at": created_at,
                },
            )
        db.add(
            InterviewSession(
                job_title="Existing interview",
                job_description="Preserve this record.",
                owner_id=regular.id,
            )
        )
        db.commit()

    principal = {"profile": admin}

    def get_test_db():
        with factory() as db:
            yield db

    app.dependency_overrides[auth.get_current_user] = (
        lambda: principal["profile"]
    )
    app.dependency_overrides[get_db] = get_test_db
    try:
        with TestClient(app) as client:
            yield client, factory, principal, admin, regular, revoked
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_admin_can_search_list_grant_and_revoke_access(admin_api):
    client, factory, _principal, _admin, regular, revoked = admin_api

    all_users = client.get("/api/v1/admin/users")
    assert all_users.status_code == 200
    assert all_users.json()["total"] == 3
    assert len(all_users.json()["users"]) == 3

    response = client.get("/api/v1/admin/users?search=candidate")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["users"][0]["email"] == "candidate@example.test"
    assert payload["users"][0]["is_active"] is True
    assert payload["users"][0]["role"] == "user"

    disable = client.patch(
        f"/api/v1/admin/users/{regular.id}/access",
        json={"is_active": False},
    )
    assert disable.status_code == 200
    assert disable.json()["is_active"] is False
    enable = client.patch(
        f"/api/v1/admin/users/{revoked.id}/access",
        json={"is_active": True},
    )
    assert enable.status_code == 200
    assert enable.json()["is_active"] is True

    with factory() as db:
        preserved = (
            db.query(InterviewSession)
            .filter(InterviewSession.owner_id == regular.id)
            .one()
        )
        assert preserved.job_description == "Preserve this record."
        assert db.get(UserProfile, regular.id).is_active is False
        assert db.get(UserProfile, revoked.id).is_active is True


def test_regular_user_cannot_list_or_change_user_access(admin_api):
    client, _factory, principal, _admin, regular, revoked = admin_api
    principal["profile"] = regular

    assert client.get("/api/v1/admin/users").status_code == 403
    assert client.patch(
        f"/api/v1/admin/users/{revoked.id}/access",
        json={"is_active": True},
    ).status_code == 403
    assert client.patch(
        f"/api/v1/admin/users/{regular.id}/access",
        json={"is_active": True, "role": "admin"},
    ).status_code == 403


def test_admin_cannot_change_own_access_and_invalid_inputs_are_rejected(admin_api):
    client, _factory, principal, admin, _regular, _revoked = admin_api

    own_access = client.patch(
        f"/api/v1/admin/users/{admin.id}/access",
        json={"is_active": False},
    )
    assert own_access.status_code == 409
    assert client.patch(
        "/api/v1/admin/users/not-a-uuid/access",
        json={"is_active": False},
    ).status_code == 422
    principal["profile"] = admin
    assert client.patch(
        f"/api/v1/admin/users/{admin.id}/access",
        json={"is_active": False, "role": "user"},
    ).status_code == 422
    assert client.patch(
        f"/api/v1/admin/users/{uuid4()}/access",
        json={"is_active": False},
    ).status_code == 404
    assert client.get("/api/v1/admin/users?limit=101").status_code == 422


def test_inactive_user_is_denied_and_identity_reports_current_access(admin_api):
    client, _factory, principal, _admin, _regular, revoked = admin_api
    principal["profile"] = revoked

    assert client.get("/api/v1/auth/me").json()["is_active"] is False
    assert client.get("/api/v1/admin/users").status_code == 403
    with pytest.raises(HTTPException) as error:
        auth.get_active_user(current_user=revoked)
    assert error.value.status_code == 403


def test_unauthenticated_user_cannot_access_admin_api():
    app.dependency_overrides.clear()
    with TestClient(app) as client:
        assert client.get("/api/v1/admin/users").status_code == 401
