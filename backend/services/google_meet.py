"""
Google Meet scheduling via Calendar API + free Jitsi fallback.

Env (personal Google Cloud OAuth client — not internship GCP):
  GOOGLE_CLIENT_ID
  GOOGLE_CLIENT_SECRET
  GOOGLE_REDIRECT_URI  (default http://127.0.0.1:8000/api/meeting-intel/google/callback)

Scopes: calendar.events
Tokens: data/runtime/google_oauth_tokens.json
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

from dotenv import load_dotenv

from domain.persistence import RUNTIME, _read, _write, audit

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "backend" / ".env")

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
TOKEN_FILE = "google_oauth_tokens.json"


def _client_id() -> str:
    return (os.getenv("GOOGLE_CLIENT_ID") or "").strip()


def _client_secret() -> str:
    return (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()


def redirect_uri() -> str:
    return (
        os.getenv("GOOGLE_REDIRECT_URI")
        or "http://127.0.0.1:8000/api/meeting-intel/google/callback"
    ).strip()


def is_configured() -> bool:
    return bool(_client_id() and _client_secret())


def status() -> dict[str, Any]:
    tokens = _read(TOKEN_FILE, {})
    return {
        "provider": "google_calendar_meet",
        "configured": is_configured(),
        "connected": bool(tokens.get("refresh_token") or tokens.get("token")),
        "redirect_uri": redirect_uri(),
        "env_vars": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI"],
        "fallback": "jitsi_meet_free",
        "note": (
            "With Google OAuth connected, meetings get a real Google Meet link via Calendar. "
            "Without it, a free Jitsi room is created so demos still work."
        ),
    }


def auth_url(state: str | None = None) -> dict[str, Any]:
    if not is_configured():
        return {
            "error": "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET not set",
            "status": status(),
        }
    st = state or uuid4().hex
    params = {
        "client_id": _client_id(),
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": st,
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return {"auth_url": url, "state": st, "status": status()}


def exchange_code(code: str) -> dict[str, Any]:
    if not is_configured():
        return {"error": "Google OAuth not configured"}
    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError as e:
        return {"error": f"google-auth-oauthlib missing: {e}"}

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": _client_id(),
                "client_secret": _client_secret(),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri()],
            }
        },
        scopes=SCOPES,
        redirect_uri=redirect_uri(),
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    payload = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or SCOPES),
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    # Keep prior refresh_token if Google omits it on re-consent
    prior = _read(TOKEN_FILE, {})
    if not payload.get("refresh_token") and prior.get("refresh_token"):
        payload["refresh_token"] = prior["refresh_token"]
    _write(TOKEN_FILE, payload)
    audit("google_oauth_connected", {"scopes": payload["scopes"]})
    return {"ok": True, "status": status()}


def _credentials():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    data = _read(TOKEN_FILE, {})
    if not data.get("token") and not data.get("refresh_token"):
        return None
    creds = Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri") or "https://oauth2.googleapis.com/token",
        client_id=data.get("client_id") or _client_id(),
        client_secret=data.get("client_secret") or _client_secret(),
        scopes=data.get("scopes") or SCOPES,
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        data["token"] = creds.token
        data["expiry"] = creds.expiry.isoformat() if creds.expiry else None
        _write(TOKEN_FILE, data)
    return creds


def create_google_meet(
    *,
    title: str,
    description: str,
    start_iso: str | None,
    duration_min: int = 45,
    attendee_emails: list[str] | None = None,
) -> dict[str, Any]:
    """Create Calendar event with Google Meet conference."""
    creds = _credentials()
    if not creds:
        return {
            "error": "Google account not connected — open /api/meeting-intel/google/auth-url",
            "status": status(),
        }
    try:
        from googleapiclient.discovery import build
    except ImportError as e:
        return {"error": f"google-api-python-client missing: {e}"}

    start = _parse_start(start_iso)
    end = start + timedelta(minutes=max(15, int(duration_min or 45)))
    body: dict[str, Any] = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start.isoformat(), "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": end.isoformat(), "timeZone": "Asia/Kolkata"},
        "conferenceData": {
            "createRequest": {
                "requestId": uuid4().hex,
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }
    if attendee_emails:
        body["attendees"] = [{"email": e} for e in attendee_emails if e]

    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    event = (
        service.events()
        .insert(calendarId="primary", body=body, conferenceDataVersion=1, sendUpdates="none")
        .execute()
    )
    meet_link = (
        (event.get("hangoutLink") or "")
        or _extract_meet_link(event)
        or ""
    )
    if not meet_link:
        return {"error": "Calendar event created but Meet link missing", "event": event}

    audit("google_meet_created", {"event_id": event.get("id")})
    return {
        "provider": "google_meet",
        "meet_link": meet_link,
        "calendar_event_id": event.get("id"),
        "html_link": event.get("htmlLink"),
        "start": event.get("start"),
        "end": event.get("end"),
        "is_demo": False,
    }


def create_jitsi_room(meeting_id: str, title: str) -> dict[str, Any]:
    """Free Jitsi room — works without Google OAuth for demos."""
    room = f"AdvisorPulse-{meeting_id}".replace(" ", "")
    link = f"https://meet.jit.si/{room}"
    return {
        "provider": "jitsi",
        "meet_link": link,
        "calendar_event_id": None,
        "html_link": link,
        "room": room,
        "title": title,
        "is_demo": True,
        "note": "Free Jitsi room (no Google account required). Anyone with the link can join.",
    }


def schedule_video_meeting(
    *,
    meeting_id: str,
    title: str,
    description: str = "",
    start_iso: str | None = None,
    duration_min: int = 45,
    prefer_google: bool = True,
) -> dict[str, Any]:
    if prefer_google and is_configured() and status().get("connected"):
        result = create_google_meet(
            title=title,
            description=description or f"Advisor Pulse meeting {meeting_id}",
            start_iso=start_iso,
            duration_min=duration_min,
        )
        if not result.get("error"):
            return result
        # Fall through to Jitsi with reason
        result_jitsi = create_jitsi_room(meeting_id, title)
        result_jitsi["google_error"] = result.get("error")
        result_jitsi["fallback_reason"] = "Google Meet failed — using free Jitsi"
        return result_jitsi

    jitsi = create_jitsi_room(meeting_id, title)
    if prefer_google and is_configured() and not status().get("connected"):
        jitsi["fallback_reason"] = "Google OAuth not connected — using free Jitsi"
        jitsi["connect_hint"] = "Call GET /api/meeting-intel/google/auth-url to connect Calendar"
    elif not is_configured():
        jitsi["fallback_reason"] = "GOOGLE_CLIENT_ID/SECRET not set — using free Jitsi"
    return jitsi


def _parse_start(start_iso: str | None) -> datetime:
    if start_iso:
        try:
            s = start_iso.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass
    return datetime.now(timezone.utc) + timedelta(minutes=5)


def _extract_meet_link(event: dict[str, Any]) -> str | None:
    ep = event.get("conferenceData", {}).get("entryPoints") or []
    for p in ep:
        if p.get("entryPointType") == "video" and p.get("uri"):
            return p["uri"]
    return None
