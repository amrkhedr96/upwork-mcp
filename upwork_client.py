"""Official Upwork GraphQL client. Tokens stay on disk and are never returned."""

from __future__ import annotations

import json
import time
import urllib.parse
from pathlib import Path
from typing import Any

import httpx

AUTH_URL = "https://www.upwork.com/ab/account-security/oauth2/authorize"
TOKEN_URL = "https://www.upwork.com/api/v3/oauth2/token"
GRAPHQL_URL = "https://api.upwork.com/graphql"
DEFAULT_REDIRECT = "https://www.upwork.com/ab/messages/rooms/"


class UpworkError(Exception):
    pass


class Store:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or (Path.home() / ".upwork-mcp")

    @property
    def config_path(self) -> Path:
        return self.root / "config.json"

    @property
    def token_path(self) -> Path:
        return self.root / "token.json"

    def load_config(self) -> dict[str, str]:
        if not self.config_path.exists():
            return {}
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise UpworkError("config.json must be an object")
        return {str(k): str(v) for k, v in data.items() if v is not None}

    def save_config(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        if not client_id.strip() or not client_secret.strip():
            raise UpworkError("client_id and client_secret are required")
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {
            "client_id": client_id.strip(),
            "client_secret": client_secret.strip(),
            "redirect_uri": (redirect_uri or DEFAULT_REDIRECT).strip(),
        }
        self.config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load_token(self) -> dict[str, Any]:
        if not self.token_path.exists():
            return {}
        data = json.loads(self.token_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}

    def save_token(self, token: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(json.dumps(token, indent=2), encoding="utf-8")


def auth_url(client_id: str, redirect_uri: str) -> str:
    query = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri or DEFAULT_REDIRECT,
        }
    )
    return f"{AUTH_URL}?{query}"


def token_form(config: dict[str, str], *, code: str = "", refresh_token: str = "") -> dict[str, str]:
    if code:
        return {
            "grant_type": "authorization_code",
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "code": code,
            "redirect_uri": config.get("redirect_uri") or DEFAULT_REDIRECT,
        }
    if refresh_token:
        return {
            "grant_type": "refresh_token",
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "refresh_token": refresh_token,
        }
    raise UpworkError("token request needs an authorization code or a refresh token")


def stamp_expiry(payload: dict[str, Any], now: float | None = None) -> dict[str, Any]:
    body = dict(payload)
    expires_in = int(body.get("expires_in") or 86400)
    body["expires_at"] = int((now if now is not None else time.time()) + max(expires_in - 60, 30))
    return body


def proposal_input(
    *,
    job_reference: str,
    cover_letter: str,
    charged_amount: float,
    contractor_id: str,
    odesk_user_id: str,
    team_org_id: str,
    estimated_duration: int | None = None,
    questions: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    if len(cover_letter.strip()) < 50:
        raise UpworkError("cover letter must be at least 50 characters")
    if charged_amount <= 0:
        raise UpworkError("charged_amount must be greater than 0")
    body: dict[str, Any] = {
        "selectedContractor": {"id": contractor_id, "oDeskUserID": odesk_user_id},
        "jobReference": job_reference,
        "chargedAmount": charged_amount,
        "coverLetter": cover_letter.strip(),
        "teamOrgId": team_org_id,
    }
    if estimated_duration is not None:
        body["estimatedDuration"] = estimated_duration
    if questions:
        body["questions"] = questions
    return body


class UpworkClient:
    def __init__(self, store: Store | None = None, http: httpx.Client | None = None) -> None:
        self.store = store or Store()
        self.http = http or httpx.Client(timeout=30)

    def close(self) -> None:
        self.http.close()

    def status(self) -> dict[str, Any]:
        config = self.store.load_config()
        token = self.store.load_token()
        client_id = config.get("client_id", "")
        return {
            "configured": bool(client_id and config.get("client_secret")),
            "client_id_tail": client_id[-4:] if client_id else "",
            "redirect_uri": config.get("redirect_uri") or DEFAULT_REDIRECT,
            "authorized": bool(token.get("access_token")),
            "expires_at": token.get("expires_at"),
            "config_path": str(self.store.config_path),
            "token_path": str(self.store.token_path),
        }

    def begin_auth(self) -> str:
        config = self._require_config()
        return auth_url(config["client_id"], config.get("redirect_uri") or DEFAULT_REDIRECT)

    def exchange_code(self, code: str) -> dict[str, Any]:
        config = self._require_config()
        saved = self._post_token(token_form(config, code=code.strip()))
        return {"authorized": True, "expires_at": saved.get("expires_at")}

    def graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        token = self._access_token()
        headers = {
            "Authorization": f"Bearer {token['access_token']}",
            "Content-Type": "application/json",
        }
        tenant = token.get("tenant_id")
        if tenant:
            headers["X-Upwork-API-TenantId"] = str(tenant)
        response = self.http.post(
            GRAPHQL_URL,
            headers=headers,
            json={"query": query, "variables": variables or {}},
        )
        if response.status_code == 429:
            raise UpworkError("Upwork rate limit (429). Wait a minute and retry.")
        if response.status_code >= 400:
            raise UpworkError(f"Upwork HTTP {response.status_code}: {response.text[:400]}")
        body = response.json()
        if body.get("errors"):
            message = "; ".join(str(item.get("message", item)) for item in body["errors"])
            raise UpworkError(message)
        return body.get("data") or {}

    def remember_tenant(self, tenant_id: str) -> None:
        token = self.store.load_token()
        if not token.get("access_token"):
            raise UpworkError("authorize before setting the organization id")
        token["tenant_id"] = tenant_id
        self.store.save_token(token)

    def _require_config(self) -> dict[str, str]:
        config = self.store.load_config()
        if not config.get("client_id") or not config.get("client_secret"):
            raise UpworkError(
                "No API key saved. Apply at https://www.upwork.com/developer/keys/apply "
                "then call upwork_save_credentials. The account currently has zero keys."
            )
        return config

    def _access_token(self) -> dict[str, Any]:
        token = self.store.load_token()
        if not token.get("access_token"):
            raise UpworkError("Not authorized. Open upwork_auth_url, approve, then upwork_exchange_code.")
        expires_at = int(token.get("expires_at") or 0)
        if expires_at and expires_at <= int(time.time()) and token.get("refresh_token"):
            config = self._require_config()
            token = self._post_token(token_form(config, refresh_token=str(token["refresh_token"])))
        return token

    def _post_token(self, form: dict[str, str]) -> dict[str, Any]:
        response = self.http.post(TOKEN_URL, data=form, headers={"Accept": "application/json"})
        if response.status_code >= 400:
            raise UpworkError(f"Token request failed ({response.status_code}): {response.text[:400]}")
        payload = response.json()
        if "access_token" not in payload:
            raise UpworkError("Token response had no access_token")
        previous = self.store.load_token()
        saved = stamp_expiry(payload)
        if previous.get("tenant_id") and "tenant_id" not in saved:
            saved["tenant_id"] = previous["tenant_id"]
        if not saved.get("refresh_token") and previous.get("refresh_token"):
            saved["refresh_token"] = previous["refresh_token"]
        self.store.save_token(saved)
        return saved
