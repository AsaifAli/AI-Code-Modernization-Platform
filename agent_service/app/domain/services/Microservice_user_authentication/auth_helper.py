from fastapi import Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os

import httpx

from app.infrastructure.utils.auth_client import (
    get_current_user_http,
    github_token_scheme,
)

security = HTTPBearer()


# ---------------- CURRENT USER (via auth service HTTP) ----------------
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Delegate to auth_client (HTTP-based validation via auth_service)."""
    return get_current_user_http(credentials)

async def get_current_github_user(
    github_token: str = Security(github_token_scheme)
):
    """Return GitHub/GitLab user only if token is provided"""

    # ✅ If header is missing → DO NOTHING
    if not github_token:
        return None

    async with httpx.AsyncClient() as client:
        
        # ----------------------------
        # 1) Try GitHub (public)
        # ----------------------------
        resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {github_token}"}
        )
        if resp.status_code == 200:
            data = resp.json()
            data.update({"platform": "github"})
            return data

        # ----------------------------
        # 2) Try GitLab (public)
        # ----------------------------
        resp = await client.get(
            "https://gitlab.com/api/v4/user",
            headers={"Authorization": f"Bearer {github_token}"}
        )
        if resp.status_code == 200:
            data = resp.json()
            data.update({"platform": "gitlab"})
            return data

        # ----------------------------
        # 3) Try Self-hosted GitLab
        # ----------------------------
        self_hosted_base_url = os.getenv("GITLAB_SELF_HOSTED_BASE_URL", "").rstrip("/")
        if self_hosted_base_url:
            resp = await client.get(
                f"{self_hosted_base_url}/api/v4/user",
                headers={"Authorization": f"Bearer {github_token}"},
            )
        else:
            resp = None
        if resp is not None and resp.status_code == 200:
            data = resp.json()
            data.update({"platform": "gitlab", "self_hosted": True})
            return data

    return None
