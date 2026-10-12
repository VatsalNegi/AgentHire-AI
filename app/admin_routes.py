from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_db
from app.models import UserProfile


router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
)


class AdminUser(BaseModel):
    id: UUID
    email: str
    created_at: datetime
    role: Literal["admin", "user"]
    is_active: bool


class AdminUserList(BaseModel):
    users: list[AdminUser]
    total: int
    offset: int
    limit: int


class AccessUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool


@router.get("/users", response_model=AdminUserList)
def list_users(
    search: str | None = Query(default=None, min_length=1, max_length=254),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    _admin: UserProfile = Depends(require_admin),
    db: Session = Depends(get_db),
):
    normalized_search = search.strip().lower() if search else None
    if normalized_search == "":
        normalized_search = None
    filters = """
        FROM auth.users AS auth_user
        JOIN user_profiles AS profile
          ON profile.id = auth_user.id
    """
    parameters = {}
    if normalized_search:
        escaped_search = (
            normalized_search.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        email_pattern = f"%{escaped_search}%"
        filters += (
            "\nWHERE lower(auth_user.email) "
            "LIKE :email_pattern ESCAPE '\\'"
        )
        parameters["email_pattern"] = email_pattern
    total = db.execute(
        text(f"SELECT count(*) {filters}"),
        parameters,
    ).scalar_one()
    rows = db.execute(
        text(
            f"""
            SELECT auth_user.id, auth_user.email, auth_user.created_at,
                   profile.role, profile.is_active
            {filters}
            ORDER BY lower(auth_user.email), auth_user.id
            LIMIT :limit OFFSET :offset
            """
        ),
        {**parameters, "offset": offset, "limit": limit},
    ).mappings()
    return AdminUserList(
        users=[
            AdminUser(
                id=row["id"],
                email=row["email"],
                created_at=row["created_at"],
                role=row["role"],
                is_active=row["is_active"],
            )
            for row in rows
        ],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.patch(
    "/users/{user_id}/access",
    response_model=AdminUser,
)
def update_user_access(
    user_id: UUID,
    request: AccessUpdate,
    admin: UserProfile = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Administrators cannot change their own access.",
        )

    profile = db.get(UserProfile, user_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found.",
        )

    profile.is_active = request.is_active
    db.commit()
    db.refresh(profile)
    row = db.execute(
        text(
            """
            SELECT auth_user.email, auth_user.created_at
            FROM auth.users AS auth_user
            WHERE auth_user.id = :user_id
            """
        ),
        {
            "user_id": (
                user_id
                if db.get_bind().dialect.name == "postgresql"
                else user_id.hex
            )
        },
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    return AdminUser(
        id=profile.id,
        email=row["email"],
        created_at=row["created_at"],
        role=profile.role,
        is_active=profile.is_active,
    )
