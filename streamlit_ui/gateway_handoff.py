"""Secure one-time portfolio Gateway session exchange for LegacyLens."""
from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

PROJECT = "legacylens"
TIMEOUT_SECONDS = 8
MAX_RESPONSE_BYTES = 64 * 1024
CODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


class GatewayHandoffError(RuntimeError):
    """Safe-to-display portfolio Gateway handoff error."""


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _exchange_endpoint(base_url: str) -> str:
    try:
        parsed = urlsplit((base_url or "").strip())
        hostname = parsed.hostname
        _ = parsed.port
    except ValueError as exc:
        raise GatewayHandoffError("The portfolio Gateway URL is invalid.") from exc

    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.netloc
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise GatewayHandoffError("The portfolio Gateway URL is invalid.")
    if os.getenv("NODE_ENV", "").lower() == "production" and parsed.scheme != "https":
        raise GatewayHandoffError("The portfolio Gateway must use HTTPS in production.")

    path = parsed.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3].rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, f"{path}/v1/demo/session/exchange", "", ""))


def exchange_handoff_code(code: str, *, gateway_url: str | None = None) -> dict[str, Any]:
    code = str(code or "").strip()
    if not CODE_PATTERN.fullmatch(code):
        raise GatewayHandoffError("The LegacyLens launch code is invalid or incomplete. Launch again from the website.")

    base_url = (gateway_url or os.getenv("PORTFOLIO_SESSION_GATEWAY_URL", "")).strip()
    if not base_url:
        raise GatewayHandoffError("Portfolio session exchange is not configured on LegacyLens.")

    request = Request(
        _exchange_endpoint(base_url),
        data=json.dumps({"code": code, "project": PROJECT}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
        },
        method="POST",
    )

    try:
        with build_opener(_NoRedirectHandler()).open(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        if exc.code == 401:
            raise GatewayHandoffError("The LegacyLens launch code expired, was used, or is invalid. Launch again from the website.") from None
        raise GatewayHandoffError("The portfolio Gateway could not complete the LegacyLens session exchange.") from None
    except (URLError, TimeoutError, OSError):
        raise GatewayHandoffError("The AI Gateway could not be reached. Retry the launch from the website.") from None

    if len(raw) > MAX_RESPONSE_BYTES:
        raise GatewayHandoffError("The Gateway returned an invalid LegacyLens session response.")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise GatewayHandoffError("The Gateway returned an invalid LegacyLens session response.") from None
    if not isinstance(payload, dict):
        raise GatewayHandoffError("The Gateway returned an invalid LegacyLens session response.")

    token = payload.get("access_token")
    target = payload.get("target_project")
    expires = payload.get("expires_in")
    if not isinstance(token, str) or not token.strip() or len(token) > 8192 or any(ch.isspace() for ch in token):
        raise GatewayHandoffError("The Gateway did not return a valid LegacyLens session.")
    if target != PROJECT:
        raise GatewayHandoffError("The Gateway returned a session for an unexpected project.")
    if isinstance(expires, bool) or not isinstance(expires, int) or not 1 <= expires <= 3600:
        raise GatewayHandoffError("The Gateway returned an invalid session expiry.")

    return {"access_token": token, "expires_in": expires, "target_project": target}
