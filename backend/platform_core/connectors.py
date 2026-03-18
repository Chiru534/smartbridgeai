from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

try:
    import backend.models as models
except ImportError:
    import models

from .config import settings

try:
    from google.auth.transport.requests import Request as GoogleAuthRequest
    from google.oauth2 import service_account
except Exception:  # pragma: no cover - optional until dependency is installed
    GoogleAuthRequest = None
    service_account = None


GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_URL = "https://api.github.com"
GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_DRIVE_API_URL = "https://www.googleapis.com/drive/v3"
GOOGLE_DRIVE_CONTENT_SCOPES = {
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.readonly",
}


@dataclass
class OAuthStateRecord:
    connector_name: str
    username: str
    created_at: datetime


_oauth_state_cache: dict[str, OAuthStateRecord] = {}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _cleanup_states() -> None:
    cutoff = _utcnow() - timedelta(seconds=settings.oauth_state_ttl_secs)
    for state, payload in list(_oauth_state_cache.items()):
        if payload.created_at < cutoff:
            _oauth_state_cache.pop(state, None)


def issue_oauth_state(connector_name: str, username: str) -> str:
    _cleanup_states()
    state = secrets.token_urlsafe(32)
    _oauth_state_cache[state] = OAuthStateRecord(
        connector_name=connector_name,
        username=username,
        created_at=_utcnow(),
    )
    return state


def pop_oauth_state(state: str, connector_name: str) -> OAuthStateRecord:
    _cleanup_states()
    payload = _oauth_state_cache.pop(state, None)
    if payload is None or payload.connector_name != connector_name:
        raise ValueError("The OAuth state is invalid or has expired")
    return payload


def connector_redirect_uri(connector_name: str) -> str:
    return f"{settings.public_backend_url}/api/oauth/{connector_name}/callback"


def connector_display_name(connector_name: str) -> str:
    return "Google Drive" if connector_name == "google_drive" else "GitHub"


def is_connector_oauth_configured(connector_name: str) -> bool:
    if connector_name == "github":
        return bool(settings.github_client_id and settings.github_client_secret)
    if connector_name == "google_drive":
        return bool(settings.google_client_id and settings.google_client_secret)
    return False


def is_connector_pat_configured(connector_name: str) -> bool:
    if connector_name == "github":
        return bool(settings.github_pat)
    return False


def is_google_service_account_configured() -> bool:
    return bool(
        settings.google_service_account_email
        and (settings.google_service_account_json or settings.google_service_account_json_path)
    )


def has_google_service_account_email() -> bool:
    return bool(settings.google_service_account_email)


def is_google_service_account_runtime_ready() -> bool:
    return is_google_service_account_configured() and service_account is not None and GoogleAuthRequest is not None


def google_drive_service_account_summary() -> dict[str, Any] | None:
    if not is_google_service_account_configured():
        return None
    return {
        "email": settings.google_service_account_email,
        "root_folder_id": settings.google_drive_root_folder_id or None,
        "runtime_ready": is_google_service_account_runtime_ready(),
    }


def connector_setup_hint(connector_name: str) -> str:
    if connector_name == "github":
        callback_uri = connector_redirect_uri("github")
        return (
            f"Create a GitHub OAuth app and set its callback URL to {callback_uri}. "
            "Then place the client ID and client secret in backend/.env. "
            "Alternatively, set GITHUB_PAT in backend/.env to use a shared local token without the OAuth popup."
        )
    callback_uri = connector_redirect_uri("google")
    if has_google_service_account_email() and not is_google_service_account_configured():
        return (
            "A Google service-account email is configured, but no service-account key is configured. "
            "Add GOOGLE_SERVICE_ACCOUNT_JSON_PATH or GOOGLE_SERVICE_ACCOUNT_JSON in backend/.env. "
            "Until then, the app will keep using the Google OAuth popup instead of direct folder access."
        )
    if is_google_service_account_configured():
        if is_google_service_account_runtime_ready():
            return (
                "Google Drive is configured in service-account mode. "
                "Share the target Drive folder with the configured service account email so the local MCP server can access it directly."
            )
        return (
            "A Google service account is configured, but the 'google-auth' package is not available in the backend environment. "
            "Install google-auth to enable direct Drive access."
        )
    return (
        f"Create a Google OAuth client and add {callback_uri} as an authorized redirect URI. "
        "Then place the Google client ID and client secret in backend/.env, or configure a service account JSON key for direct Drive access."
    )


def build_github_authorize_url(state: str) -> str:
    params = {
        "client_id": settings.github_client_id,
        "redirect_uri": connector_redirect_uri("github"),
        "scope": settings.github_oauth_scope,
        "state": state,
    }
    return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"


def build_google_authorize_url(state: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": connector_redirect_uri("google"),
        "response_type": "code",
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "scope": settings.google_oauth_scope,
        "state": state,
    }
    return f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_github_code(code: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            GITHUB_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
                "redirect_uri": connector_redirect_uri("github"),
            },
        )
        response.raise_for_status()
        token_data = response.json()
        if token_data.get("error"):
            raise ValueError(token_data.get("error_description") or token_data["error"])
        return token_data


async def exchange_google_code(code: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": connector_redirect_uri("google"),
            },
        )
        response.raise_for_status()
        token_data = response.json()
        if token_data.get("error"):
            error_description = token_data.get("error_description") or token_data["error"]
            raise ValueError(error_description)
        return token_data


async def refresh_google_access_token(refresh_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
        token_data = response.json()
        if token_data.get("error"):
            error_description = token_data.get("error_description") or token_data["error"]
            raise ValueError(error_description)
        return token_data


async def fetch_github_profile(access_token: str) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        profile_response = await client.get(f"{GITHUB_API_URL}/user", headers=headers)
        profile_response.raise_for_status()
        emails_response = await client.get(f"{GITHUB_API_URL}/user/emails", headers=headers)
        email = None
        if emails_response.status_code == 200:
            emails = emails_response.json()
            primary = next((item for item in emails if item.get("primary")), None)
            email = (primary or (emails[0] if emails else {})).get("email")
        profile = profile_response.json()
        profile["email"] = profile.get("email") or email
        scopes = profile_response.headers.get("x-oauth-scopes")
        if scopes:
            profile["scopes"] = scopes
        return profile


async def fetch_google_profile(access_token: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        userinfo_response = await client.get("https://www.googleapis.com/oauth2/v2/userinfo", headers=headers)
        userinfo_response.raise_for_status()
        about_response = await client.get(
            f"{GOOGLE_DRIVE_API_URL}/about",
            headers=headers,
            params={"fields": "user,storageQuota"},
        )
        try:
            about_response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 403:
                raise RuntimeError(
                    "Google Drive API access was denied. Enable the Google Drive API in the Google Cloud project "
                    "for this OAuth client, confirm the Drive scopes are approved on the OAuth consent screen, "
                    "and then retry the connection."
                ) from exc
            raise
        userinfo = userinfo_response.json()
        about = about_response.json()
        userinfo["drive_user"] = about.get("user") or {}
        userinfo["storage_quota"] = about.get("storageQuota") or {}
        return userinfo


def _load_google_service_account_info() -> dict[str, Any] | None:
    if settings.google_service_account_json:
        try:
            parsed = json.loads(settings.google_service_account_json)
        except json.JSONDecodeError as exc:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON must decode to a JSON object")
        return parsed

    if settings.google_service_account_json_path:
        try:
            with open(settings.google_service_account_json_path, "r", encoding="utf-8") as handle:
                parsed = json.load(handle)
        except FileNotFoundError as exc:
            raise ValueError(f"Google service account key file was not found: {settings.google_service_account_json_path}") from exc
        except json.JSONDecodeError as exc:
            raise ValueError("Google service account key file is not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("Google service account key file must contain a JSON object")
        return parsed

    return None


def _google_scopes_for_service_account() -> list[str]:
    return [scope for scope in settings.google_oauth_scope.split() if scope]


def _get_google_service_account_credentials():
    if not is_google_service_account_runtime_ready():
        raise RuntimeError("Google service account mode is not ready")

    service_account_info = _load_google_service_account_info()
    if not service_account_info:
        raise RuntimeError("Google service account credentials are missing")

    if settings.google_service_account_email and service_account_info.get("client_email") != settings.google_service_account_email:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_EMAIL does not match the service account key")

    return service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=_google_scopes_for_service_account(),
    )


def _parse_config(account: models.ConnectorAccountDB | None) -> dict[str, Any]:
    if account is None or not account.config_json:
        return {}
    try:
        parsed = json.loads(account.config_json)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def upsert_connector_account(
    db: Session,
    username: str,
    connector_name: str,
    auth_method: str,
    config: dict[str, Any],
) -> models.ConnectorAccountDB:
    account = (
        db.query(models.ConnectorAccountDB)
        .filter(
            models.ConnectorAccountDB.username == username,
            models.ConnectorAccountDB.connector_name == connector_name,
        )
        .first()
    )
    if account is None:
        account = models.ConnectorAccountDB(
            username=username,
            connector_name=connector_name,
            auth_method=auth_method,
            config_json=json.dumps(config),
        )
        db.add(account)
    else:
        account.auth_method = auth_method
        account.config_json = json.dumps(config)
        account.updated_at = _utcnow()
    db.commit()
    db.refresh(account)
    return account


def get_connector_account(db: Session, username: str, connector_name: str) -> models.ConnectorAccountDB | None:
    return (
        db.query(models.ConnectorAccountDB)
        .filter(
            models.ConnectorAccountDB.username == username,
            models.ConnectorAccountDB.connector_name == connector_name,
        )
        .first()
    )


def remove_connector_account(db: Session, username: str, connector_name: str) -> None:
    account = get_connector_account(db, username, connector_name)
    if account is None:
        return
    db.delete(account)
    db.commit()


def get_connector_accounts_summary(db: Session, username: str) -> list[dict[str, Any]]:
    results = []
    for connector_name in ("github", "google_drive"):
        account = get_connector_account(db, username, connector_name)
        config = _parse_config(account)
        if connector_name == "github" and account is None and settings.github_pat:
            results.append(
                {
                    "connector_name": connector_name,
                    "connected": True,
                    "auth_method": "pat_env",
                    "display_name": "Shared GitHub PAT",
                    "login": None,
                    "email": None,
                    "created_at": None,
                    "updated_at": None,
                }
            )
            continue
        if connector_name == "google_drive" and account is None and is_google_service_account_runtime_ready():
            service_account_summary = google_drive_service_account_summary() or {}
            results.append(
                {
                    "connector_name": connector_name,
                    "connected": True,
                    "auth_method": "service_account",
                    "display_name": "Google Drive Service Account",
                    "login": service_account_summary.get("email"),
                    "email": service_account_summary.get("email"),
                    "created_at": None,
                    "updated_at": None,
                }
            )
            continue
        results.append(
            {
                "connector_name": connector_name,
                "connected": account is not None,
                "auth_method": account.auth_method if account else None,
                "display_name": config.get("display_name"),
                "login": config.get("login"),
                "email": config.get("email"),
                "created_at": account.created_at if account else None,
                "updated_at": account.updated_at if account else None,
            }
        )
    return results


def google_drive_has_content_scope(db: Session, username: str) -> bool:
    account = get_connector_account(db, username, "google_drive")
    if account is None:
        if is_google_service_account_runtime_ready():
            return bool(set(_google_scopes_for_service_account()).intersection(GOOGLE_DRIVE_CONTENT_SCOPES))
        return False

    config = _parse_config(account)
    scope_value = str(config.get("scope") or "")
    granted_scopes = {scope.strip() for scope in scope_value.split() if scope.strip()}
    return bool(granted_scopes.intersection(GOOGLE_DRIVE_CONTENT_SCOPES))


def require_connector_token(db: Session, username: str, connector_name: str) -> dict[str, Any]:
    account = get_connector_account(db, username, connector_name)
    if account is None and connector_name == "github" and settings.github_pat:
        return {
            "access_token": settings.github_pat,
            "auth_method": "pat_env",
            "display_name": "Shared GitHub PAT",
        }
    if account is None:
        raise RuntimeError(f"{connector_name} is not connected for user '{username}'")
    config = _parse_config(account)
    if not config.get("access_token") and connector_name != "google_drive":
        raise RuntimeError(f"{connector_name} access token is missing")
    return config


async def get_google_access_token(db: Session, username: str) -> str:
    if is_google_service_account_runtime_ready():
        credentials = _get_google_service_account_credentials()
        credentials.refresh(GoogleAuthRequest())
        if not credentials.token:
            raise RuntimeError("Failed to obtain a Google service account access token")
        return credentials.token

    account = get_connector_account(db, username, "google_drive")
    if account is None:
        raise RuntimeError("google_drive is not connected")

    config = _parse_config(account)
    refresh_token = config.get("refresh_token")
    access_token = config.get("access_token")
    expires_at = config.get("expires_at")
    if access_token and expires_at:
        try:
            parsed_expiry = datetime.fromisoformat(expires_at)
            if parsed_expiry.tzinfo is None:
                parsed_expiry = parsed_expiry.replace(tzinfo=timezone.utc)
            if parsed_expiry > _utcnow() + timedelta(seconds=60):
                return access_token
        except ValueError:
            pass

    if not refresh_token:
        raise RuntimeError("google_drive refresh token is missing")

    refreshed = await refresh_google_access_token(refresh_token)
    config["access_token"] = refreshed["access_token"]
    config["expires_at"] = (_utcnow() + timedelta(seconds=int(refreshed.get("expires_in", 3600)))).isoformat()
    if refreshed.get("refresh_token"):
        config["refresh_token"] = refreshed["refresh_token"]
    account.config_json = json.dumps(config)
    account.updated_at = _utcnow()
    db.add(account)
    db.commit()
    return config["access_token"]


def connector_success_html(connector_name: str) -> str:
    frontend_origin = settings.frontend_url.rstrip("/")
    display_name = connector_display_name(connector_name)
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>{display_name} Connected</title>
    <style>
      body {{ font-family: Arial, sans-serif; background: #0f172a; color: #e5e7eb; display: grid; place-items: center; min-height: 100vh; margin: 0; }}
      .card {{ background: rgba(15, 23, 42, 0.92); border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 16px; padding: 24px; width: min(420px, calc(100vw - 32px)); box-shadow: 0 20px 60px rgba(0,0,0,0.35); }}
      h1 {{ margin: 0 0 8px; font-size: 22px; }}
      p {{ margin: 0; color: #cbd5e1; }}
    </style>
  </head>
  <body>
    <div class="card">
      <h1>{display_name} connected</h1>
      <p>You can close this window and return to Smartbridge.</p>
    </div>
    <script>
      if (window.opener) {{
        window.opener.postMessage({{ type: "connector_connected", connector: "{connector_name}" }}, "{frontend_origin}");
      }}
      setTimeout(() => window.close(), 600);
    </script>
  </body>
</html>"""


def connector_error_html(connector_name: str, message: str) -> str:
    frontend_origin = settings.frontend_url.rstrip("/")
    display_name = connector_display_name(connector_name)
    safe_message = (message or "The connector could not be completed.").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>{display_name} Connection Error</title>
    <style>
      body {{ font-family: Arial, sans-serif; background: #0f172a; color: #e5e7eb; display: grid; place-items: center; min-height: 100vh; margin: 0; }}
      .card {{ background: rgba(15, 23, 42, 0.92); border: 1px solid rgba(248, 113, 113, 0.15); border-radius: 16px; padding: 24px; width: min(460px, calc(100vw - 32px)); box-shadow: 0 20px 60px rgba(0,0,0,0.35); }}
      h1 {{ margin: 0 0 8px; font-size: 22px; }}
      p {{ margin: 0; color: #cbd5e1; line-height: 1.5; }}
    </style>
  </head>
  <body>
    <div class="card">
      <h1>{display_name} connection failed</h1>
      <p>{safe_message}</p>
    </div>
    <script>
      if (window.opener) {{
        window.opener.postMessage({{ type: "connector_error", connector: "{connector_name}", message: {json.dumps(message or "")} }}, "{frontend_origin}");
      }}
    </script>
  </body>
</html>"""
