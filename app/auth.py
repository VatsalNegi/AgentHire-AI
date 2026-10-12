from functools import lru_cache
from urllib.parse import urlsplit
from uuid import UUID as UUIDValue
import logging
logger = logging.getLogger(__name__)
import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError, PyJWKClient, PyJWKClientError
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import UserProfile


class AuthSettings(BaseSettings):
    supabase_url: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


auth_settings = AuthSettings()
bearer_scheme = HTTPBearer(auto_error=False)


def _supabase_endpoints(project_url: str) -> tuple[str, str]:
    parsed = urlsplit(project_url.strip().rstrip("/"))
    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or (
            parsed.scheme != "https"
            and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        )
    ):
        raise RuntimeError("SUPABASE_URL is not a valid project URL.")

    auth_base = f"{parsed.scheme}://{parsed.netloc}/auth/v1"
    return (
        f"{auth_base}/.well-known/jwks.json",
        auth_base,
    )


@lru_cache(maxsize=4)
def _jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(
        jwks_url,
        cache_jwk_set=False,
        cache_keys=False,
        timeout=5,
    )


def decode_access_token(token: str, project_url: str) -> dict:
    jwks_url, issuer = _supabase_endpoints(project_url)
    try:
        header = jwt.get_unverified_header(token)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if header.get("alg") != "ES256" or not isinstance(header.get("kid"), str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(token)
        if (
            signing_key.algorithm_name != "ES256"
            or signing_key.key_type != "EC"
            or not isinstance(
                signing_key.key,
                ec.EllipticCurvePublicKey,
            )
            or signing_key.key.curve.name != "secp256r1"
        ):
            raise InvalidTokenError("Unexpected signing key type.")

        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            issuer=issuer,
            audience="authenticated",
            options={
                "require": ["exp", "iss", "aud", "sub"],
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iss": True,
                "verify_aud": True,
                "verify_sub": True,
            },
        )
        UUIDValue(claims["sub"])
        return claims
    except (InvalidTokenError, PyJWKClientError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except Exception as exc:
        logger.exception(
            "Unexpected error during Supabase JWT verification (%s)",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication verification is temporarily unavailable.",
        ) from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> UserProfile:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not auth_settings.supabase_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured on this server.",
        )

    claims = decode_access_token(
        credentials.credentials,
        auth_settings.supabase_url,
    )
    user_id = UUIDValue(claims["sub"])
    try:
        profile = db.get(UserProfile, user_id)
    except ProgrammingError as exc:
        if getattr(exc.orig, "sqlstate", None) not in {"42P01", "42703"}:
            raise
        logger.error(
            "Authentication profile lookup failed because the profile schema "
            "is incomplete; apply the latest user profile migration."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication database schema is not initialized.",
        ) from None
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User profile is not provisioned.",
        )
    return profile


def get_active_user(
    current_user: UserProfile = Depends(get_current_user),
) -> UserProfile:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Application access has not been granted.",
        )
    return current_user


def require_admin(
    current_user: UserProfile = Depends(get_active_user),
) -> UserProfile:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access is required.",
        )
    return current_user
