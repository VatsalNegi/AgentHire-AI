import json
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import UserProfile


DEFAULT_ADMIN_EMAIL = "vatsalnegi412@gmail.com"


class BootstrapSettings(BaseSettings):
    supabase_url: str = ""
    supabase_secret_key: str = ""
    supabase_service_role_key: str = ""
    initial_admin_email: str = DEFAULT_ADMIN_EMAIL
    initial_admin_password: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class AdminUserClient(Protocol):
    def find_user_by_email(self, email: str) -> dict | None: ...

    def create_user(self, email: str, password: str) -> dict: ...


class SupabaseAdminClient:
    def __init__(self, project_url: str, secret_key: str):
        self.base_url = project_url.rstrip("/") + "/auth/v1/admin/users"
        self.secret_key = secret_key

    def _request(self, method: str, url: str, body: dict | None = None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(
            url,
            data=data,
            headers={
                "apikey": self.secret_key,
                "Authorization": f"Bearer {self.secret_key}",
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            with urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(
                f"Supabase Auth Admin API failed with HTTP {exc.code}."
            ) from None
        except (URLError, json.JSONDecodeError):
            raise RuntimeError(
                "Could not complete the Supabase Auth Admin API request."
            ) from None

    def find_user_by_email(self, email: str) -> dict | None:
        page = 1
        while True:
            url = f"{self.base_url}?{urlencode({'page': page, 'per_page': 100})}"
            result = self._request("GET", url)
            users = result.get("users") if isinstance(result, dict) else result
            if not isinstance(users, list):
                raise RuntimeError("Supabase returned an invalid users response.")
            for user in users:
                if (
                    isinstance(user, dict)
                    and str(user.get("email", "")).casefold() == email.casefold()
                ):
                    return user
            if len(users) < 100:
                return None
            page += 1

    def create_user(self, email: str, password: str) -> dict:
        result = self._request(
            "POST",
            self.base_url,
            {"email": email, "password": password, "email_confirm": True},
        )
        user = result.get("user", result) if isinstance(result, dict) else None
        if not isinstance(user, dict):
            raise RuntimeError("Supabase did not return the created user.")
        return user


def bootstrap_admin(
    client: AdminUserClient,
    db: Session,
    email: str,
    initial_password: str,
) -> UUID:
    user = client.find_user_by_email(email)
    if user is None:
        if not initial_password:
            raise ValueError(
                "INITIAL_ADMIN_PASSWORD is required to create the administrator."
            )
        user = client.create_user(email, initial_password)

    try:
        user_id = UUID(str(user["id"]))
    except (KeyError, TypeError, ValueError):
        raise RuntimeError(
            "Supabase Auth Admin API returned an invalid user identifier."
        ) from None
    if str(user.get("email", "")).casefold() != email.casefold():
        raise RuntimeError(
            "Supabase Auth Admin API returned a different email account."
        )

    statement = insert(UserProfile).values(
        id=user_id,
        role="admin",
        is_active=True,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[UserProfile.id],
        set_={"role": "admin", "is_active": True},
    )
    db.execute(statement)
    db.commit()
    return user_id


def main() -> None:
    settings = BootstrapSettings()
    secret_key = (
        settings.supabase_secret_key or settings.supabase_service_role_key
    )
    if not settings.supabase_url:
        raise SystemExit("SUPABASE_URL must be configured in the backend .env.")
    if not secret_key:
        raise SystemExit(
            "SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY must be configured."
        )
    if not settings.initial_admin_email.strip():
        raise SystemExit("INITIAL_ADMIN_EMAIL must be configured.")

    client = SupabaseAdminClient(settings.supabase_url, secret_key)
    try:
        with SessionLocal() as db:
            bootstrap_admin(
                client,
                db,
                settings.initial_admin_email.strip(),
                settings.initial_admin_password,
            )
    except Exception as exc:
        raise SystemExit(
            f"Administrator bootstrap failed ({type(exc).__name__})."
        ) from None
    print(
        "Administrator bootstrap completed. An existing account's password "
        "was not changed."
    )


if __name__ == "__main__":
    main()
