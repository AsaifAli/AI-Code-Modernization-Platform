"""
User identity resolution for the standalone agent_service.

If AUTH_SERVICE_BASE_URL is set, bearer tokens are validated against that
external auth_service (legacy multi-service deployment). Otherwise
agent_service runs with no external auth dependency: a stable local user
identity is derived from the bearer token (or a fixed default if none is
supplied), so no other service is required to be reachable.
"""
import os
import logging
import time
import hashlib
from typing import Optional

import httpx
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from app.infrastructure.utils.Constants.app_constants import AgentConstants
from app.infrastructure.utils.Constants.auth_strings import AuthStrings

logger = logging.getLogger(__name__)

AUTH_SERVICE_BASE_URL = os.getenv("AUTH_SERVICE_BASE_URL")
VALIDATE_ENDPOINT = (
    f"{AUTH_SERVICE_BASE_URL.rstrip('/')}/auth/validate"
    if AUTH_SERVICE_BASE_URL
    else None
)

security = HTTPBearer(auto_error=False)
github_token_scheme = APIKeyHeader(name=AgentConstants.GITHUB_TOKEN_HEADER, auto_error=False)


class SimpleUser:
    def __init__(self, id_: str, email: str):
        self.id = id_
        self.email = email


# Short-lived auth cache to avoid validating the same bearer token on every
# high-frequency polling request (e.g., /v1/tasks/{id}).
AUTH_VALIDATE_CACHE_TTL_SEC = int(os.getenv("AUTH_VALIDATE_CACHE_TTL_SEC", "15"))
_token_user_cache: dict[str, tuple[float, SimpleUser]] = {}


def _token_cache_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _get_cached_user(token: str) -> Optional[SimpleUser]:
    if AUTH_VALIDATE_CACHE_TTL_SEC <= 0:
        return None
    key = _token_cache_key(token)
    cached = _token_user_cache.get(key)
    if not cached:
        return None
    expires_at, user = cached
    if time.time() >= expires_at:
        _token_user_cache.pop(key, None)
        return None
    return user


def _set_cached_user(token: str, user: SimpleUser) -> None:
    if AUTH_VALIDATE_CACHE_TTL_SEC <= 0:
        return
    key = _token_cache_key(token)
    _token_user_cache[key] = (time.time() + AUTH_VALIDATE_CACHE_TTL_SEC, user)


def validate_token_http(token: str) -> Optional[SimpleUser]:
    cached_user = _get_cached_user(token)
    if cached_user:
        return cached_user

    if not VALIDATE_ENDPOINT:
        logger.warning("AUTH_SERVICE_BASE_URL not set; cannot validate token")
        return None
    try:
        resp = httpx.get(
            VALIDATE_ENDPOINT,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        user = SimpleUser(id_=str(data["id"]), email=data.get("email", ""))
        _set_cached_user(token, user)
        return user
    except Exception as e:
        logger.warning(f"Auth validate HTTP error: {e}")
        return None


# user_id columns in Postgres (migration_data, etc.) are integer, so the local
# identity must be a numeric id, not an opaque hex/string token.
DEFAULT_LOCAL_USER_ID = 1
DEFAULT_LOCAL_USER = SimpleUser(id_=str(DEFAULT_LOCAL_USER_ID), email="local@standalone")

# Fits comfortably inside Postgres int4 (max 2147483647).
_LOCAL_USER_ID_MODULUS = 2_000_000_000


def _local_user_from_token(token: Optional[str]) -> SimpleUser:
    """Derive a stable, numeric local identity from the bearer token without calling any service."""
    if not token:
        return DEFAULT_LOCAL_USER
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    user_id = (int(digest, 16) % _LOCAL_USER_ID_MODULUS) + 1
    return SimpleUser(id_=str(user_id), email="local@standalone")


def get_current_user_http(
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    token = credentials.credentials if credentials else None

    if not AUTH_SERVICE_BASE_URL:
        # Standalone mode: no external auth_service configured.
        return _local_user_from_token(token)

    if not token:
        raise HTTPException(status_code=401, detail=AuthStrings.NOT_AUTHENTICATED)
    user = validate_token_http(token)
    if not user:
        raise HTTPException(status_code=401, detail=AuthStrings.INVALID_OR_EXPIRED_TOKEN)
    return user
