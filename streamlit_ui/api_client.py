"""Thin HTTP client wrapping agent_service's REST API."""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests

DEFAULT_BASE_URL = os.getenv("AGENT_SERVICE_URL", "http://localhost:8015")
DEFAULT_TIMEOUT = 30


class ApiError(Exception):
    def __init__(self, status_code: Optional[int], detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"[{status_code}] {detail}")


class AgentServiceClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, token: str = "streamlit-user"):
        self.base_url = base_url.rstrip("/")
        self.token = token or "streamlit-user"

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def _request(self, method: str, path: str, timeout: int = DEFAULT_TIMEOUT, **kwargs) -> Any:
        url = f"{self.base_url}{path}"
        try:
            resp = requests.request(method, url, headers=self._headers(), timeout=timeout, **kwargs)
        except requests.exceptions.RequestException as exc:
            raise ApiError(None, f"Could not reach agent_service at {self.base_url}: {exc}") from exc

        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise ApiError(resp.status_code, str(detail))

        if resp.headers.get("content-type", "").startswith("application/json"):
            return resp.json()
        return resp.content

    # --- health -------------------------------------------------------
    def health(self) -> Dict[str, Any]:
        return self._request("GET", "/v1/health", timeout=5)

    # --- migrations -----------------------------------------------------
    def list_migrations(self) -> Dict[str, Any]:
        return self._request("GET", "/v1/migration/list")

    def migration_status(self, migration_name: str) -> Dict[str, Any]:
        return self._request("GET", f"/v1/migration/status/{migration_name}")

    def delete_migration(self, migration_name: str) -> Dict[str, Any]:
        return self._request("DELETE", f"/v1/migration/temp/{migration_name}")

    def download_migration(self, migration_name: str) -> bytes:
        return self._request("GET", f"/v1/migration/download/{migration_name}", timeout=120)

    # --- workflow ---------------------------------------------------------
    def run_team(
        self,
        source_path: str,
        migration_name: str,
        description: str,
        target_language: Optional[str] = None,
        target_path: Optional[str] = None,
        github_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "source_path": source_path,
            "migration_name": migration_name,
            "description": description,
            "target_language": target_language,
            "target_path": target_path,
            "github_token": github_token,
        }
        return self._request("POST", "/v1/teams/run", json=payload)

    def task_status(self, task_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/v1/tasks/{task_id}", timeout=10)

    # --- chat ---------------------------------------------------------
    def chat_ask(
        self,
        migration_name: str,
        question: str,
        source_file_path: Optional[str] = None,
        is_target: bool = False,
    ) -> Dict[str, Any]:
        payload = {
            "migration_name": migration_name,
            "question": question,
            "source_file_path": source_file_path,
            "is_target": is_target,
        }
        return self._request("POST", "/v1/chat/ask", json=payload, timeout=120)

    # --- artifacts --------------------------------------------------------
    def migrated_analysis(self, migration_name: str) -> Dict[str, Any]:
        return self._request("GET", f"/v1/migration/analysis/{migration_name}", timeout=60)

    def semantic_verification(self, migration_name: str) -> Dict[str, Any]:
        return self._request("GET", f"/v1/migration/semantic-verification/{migration_name}", timeout=120)

    def migration_evidence(self, migration_name: str) -> Dict[str, Any]:
        return self._request("GET", f"/v1/migration/evidence/{migration_name}", timeout=60)

    def artifact(self, migration_name: str, artifact_type: str, scope: int = 1) -> Dict[str, Any]:
        params = {"artifact_type": artifact_type, "scope": scope}
        return self._request("GET", f"/v1/artifact/{migration_name}", params=params)

    # --- reports --------------------------------------------------------
    def report(self, migration_name: str, persist: bool = True, include_markdown: bool = False,
                require_migrated: bool = True) -> Dict[str, Any]:
        payload = {
            "migration_name": migration_name,
            "persist": persist,
            "include_markdown": include_markdown,
            "require_migrated": require_migrated,
        }
        return self._request("POST", "/v1/report/migration", json=payload, timeout=180)

    def showcase(self, migration_name: str, persist: bool = True) -> Dict[str, Any]:
        payload = {"migration_name": migration_name, "persist": persist}
        return self._request("POST", "/v1/showcase/migration", json=payload, timeout=180)
