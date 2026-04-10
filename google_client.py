"""
google_client.py — Google Calendar API wrapper + OAuth2.

Fully UI-independent: no widgets, no dialogs.
Communicates errors and auth events via Qt signals so the UI layer
can respond without knowing about the internals.

Public interface
----------------
    get_events(start, end)          -> list[dict]
    get_event(event_id)             -> dict | None
    create_event(data)              -> dict | None
    update_event(event_id, data)    -> dict | None
    delete_event(event_id)          -> bool
    refresh()                       -> None   (clears cache, re-fetches)

Signals
-------
    auth_required()         — browser consent flow needed (no token / revoked)
    auth_success()          — OAuth2 completed successfully
    error(message: str)     — network / API error; UI should show inline message
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from paths import Paths


# Calendar read + write scopes; Gmail read-only for M11 mail awareness
_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
]

# Google Calendar colorId → hex colour mapping (for dot display)
GOOGLE_COLORS: dict[str, str] = {
    "1":  "#7986cb",  # Lavender
    "2":  "#33b679",  # Sage
    "3":  "#8e24aa",  # Grape
    "4":  "#e67c73",  # Flamingo
    "5":  "#f6c026",  # Banana
    "6":  "#f5511d",  # Tangerine
    "7":  "#039be5",  # Peacock
    "8":  "#616161",  # Graphite
    "9":  "#3f51b5",  # Blueberry
    "10": "#ea4335",  # Tomato  ← urgent
    "11": "#0b8043",  # Basil
}
DEFAULT_COLOR = "#4285f4"  # calendar default (blue)

URGENT_COLOR_ID = "10"


def is_urgent(event: dict) -> bool:
    """Return True if an event should be treated as urgent."""
    if event.get("colorId") == URGENT_COLOR_ID:
        return True
    summary = (event.get("summary") or "").lower()
    description = (event.get("description") or "").lower()
    return "urgent" in summary or "urgent" in description


class GoogleClient(QObject):
    auth_required = pyqtSignal()
    auth_success  = pyqtSignal()
    ready         = pyqtSignal()   # emitted once the Calendar service is built
    error         = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._creds: Optional[Credentials] = None
        self._service = None
        self._cache: dict[str, list[dict]] = {}   # key = "start|end"
        self._lock = threading.Lock()
        # googleapiclient service is not thread-safe; serialize all .execute() calls.
        self._api_lock = threading.Lock()

    # ── Public API ─────────────────────────────────────────────────────────────

    def ensure_authenticated(self) -> bool:
        """
        Load credentials, refresh if needed, trigger browser flow if missing.
        Returns True when credentials are valid and ready to use.
        Call this once at startup (or whenever auth_required fires).
        """
        creds = self._load_token()

        if creds and creds.valid:
            self._creds = creds
            self._build_service()
            return True

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._save_token(creds)
                self._creds = creds
                self._build_service()
                return True
            except Exception:
                # Token is dead — fall through to browser flow
                pass

        # No valid credentials — need browser consent
        self.auth_required.emit()
        return False

    def run_auth_flow(self) -> bool:
        """
        Open browser OAuth2 consent flow. Blocks until the user approves or cancels.
        Returns True on success. Call from a thread if you don't want to block the UI.
        """
        credentials_path = Paths.credentials_json()
        if not credentials_path.exists():
            self.error.emit(
                f"credentials.json not found at {credentials_path}.\n"
                "Copy your Google API credentials file there."
            )
            return False

        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), _SCOPES
            )
            creds = flow.run_local_server(port=0, open_browser=True)
            self._save_token(creds)
            self._creds = creds
            self._build_service()
            self.auth_success.emit()
            return True
        except Exception as exc:
            self.error.emit(f"Authentication failed: {exc}")
            return False

    def get_events(
        self,
        start: datetime,
        end: datetime,
    ) -> list[dict]:
        """
        Return events between start and end (UTC datetimes).
        Results are cached for the session; call refresh() to force re-fetch.
        Returns [] on error (error signal is emitted).
        """
        if not self._service:
            return []

        cache_key = f"{start.isoformat()}|{end.isoformat()}"
        with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key]

        try:
            events: list[dict] = []
            page_token: Optional[str] = None
            while True:
                req = (
                    self._service.events()
                    .list(
                        calendarId="primary",
                        timeMin=_to_rfc3339(start),
                        timeMax=_to_rfc3339(end),
                        singleEvents=True,
                        orderBy="startTime",
                        maxResults=250,
                        pageToken=page_token,
                    )
                )
                with self._api_lock:
                    result = req.execute()
                events.extend(result.get("items", []))
                page_token = result.get("nextPageToken")
                if not page_token:
                    break
            with self._lock:
                self._cache[cache_key] = events
            return events
        except HttpError as exc:
            if exc.resp.status in (401, 403):
                # Token revoked
                self._creds = None
                self.auth_required.emit()
            else:
                self.error.emit(f"Could not reach Google Calendar ({exc.resp.status})")
            return []
        except Exception as exc:
            self.error.emit(f"Could not reach Google Calendar: {exc}")
            return []

    def create_event(self, data: dict) -> Optional[dict]:
        """
        Create an event on the primary calendar.
        data must be a valid Google Calendar Event resource body.
        Returns the created event dict or None on failure.
        """
        if not self._service:
            return None
        try:
            with self._api_lock:
                event = (
                    self._service.events()
                    .insert(calendarId="primary", body=data)
                    .execute()
                )
            self._invalidate_cache()
            return event
        except HttpError as exc:
            self._handle_http_error(exc)
            return None
        except Exception as exc:
            self.error.emit(f"Could not create event: {exc}")
            return None

    def get_event(self, event_id: str) -> Optional[dict]:
        """
        Fetch one event by ID from primary calendar.
        Returns event dict or None on failure.
        """
        if not self._service:
            return None
        try:
            with self._api_lock:
                return (
                    self._service.events()
                    .get(calendarId="primary", eventId=event_id)
                    .execute()
                )
        except HttpError as exc:
            self._handle_http_error(exc)
            return None
        except Exception as exc:
            self.error.emit(f"Could not read event: {exc}")
            return None

    def update_event(self, event_id: str, data: dict) -> Optional[dict]:
        """
        Update an existing event. data is a full or partial Event resource.
        Returns the updated event dict or None on failure.
        """
        if not self._service:
            return None
        try:
            with self._api_lock:
                event = (
                    self._service.events()
                    .update(calendarId="primary", eventId=event_id, body=data)
                    .execute()
                )
            self._invalidate_cache()
            return event
        except HttpError as exc:
            self._handle_http_error(exc)
            return None
        except Exception as exc:
            self.error.emit(f"Could not update event: {exc}")
            return None

    def delete_event(self, event_id: str) -> bool:
        """
        Delete an event by ID.
        Returns True on success, False on failure.
        """
        if not self._service:
            return False
        try:
            with self._api_lock:
                self._service.events().delete(
                    calendarId="primary", eventId=event_id
                ).execute()
            self._invalidate_cache()
            return True
        except HttpError as exc:
            self._handle_http_error(exc)
            return False
        except Exception as exc:
            self.error.emit(f"Could not delete event: {exc}")
            return False

    def refresh(self) -> None:
        """Clear the in-memory event cache. Next get_events() call will re-fetch."""
        with self._lock:
            self._cache.clear()

    # ── Internals ─────────────────────────────────────────────────────────────

    @property
    def is_ready(self) -> bool:
        return self._service is not None

    @property
    def credentials(self) -> Optional[Credentials]:
        """Return the current OAuth2 credentials (may be None before auth)."""
        return self._creds

    def revoke_and_reauth(self) -> None:
        """
        Delete stored token and start a fresh consent flow in a background thread.
        Use when scope upgrade is required (e.g. adding Gmail scope to an existing
        calendar-only token).
        """
        try:
            Paths.token_json().unlink(missing_ok=True)
        except Exception:
            pass
        self._creds = None
        self._service = None
        import threading as _threading
        _threading.Thread(target=self.run_auth_flow, daemon=True).start()

    def _build_service(self):
        # cache_discovery=False avoids temp-file caching issues in frozen builds
        self._service = build("calendar", "v3", credentials=self._creds, cache_discovery=False)
        self.ready.emit()

    def _load_token(self) -> Optional[Credentials]:
        token_path = Paths.token_json()
        if token_path.exists():
            try:
                return Credentials.from_authorized_user_file(str(token_path), _SCOPES)
            except Exception:
                return None
        return None

    def _save_token(self, creds: Credentials) -> None:
        try:
            Paths.token_json().write_text(creds.to_json())
        except Exception:
            pass  # Non-fatal; next launch will re-auth

    def _invalidate_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    def _handle_http_error(self, exc: HttpError) -> None:
        if exc.resp.status in (401, 403):
            self._creds = None
            self.auth_required.emit()
        else:
            self.error.emit(f"Could not reach Google Calendar ({exc.resp.status})")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _to_rfc3339(dt: datetime) -> str:
    """Convert a datetime to RFC 3339 string. Assumes UTC if no tzinfo."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def event_color(event: dict) -> str:
    """Return the hex colour for an event dot."""
    return GOOGLE_COLORS.get(event.get("colorId", ""), DEFAULT_COLOR)


def event_start_display(event: dict) -> str:
    """Return 'HH:MM' for timed events or 'All day' for all-day events."""
    start = event.get("start", {})
    if "dateTime" in start:
        dt = datetime.fromisoformat(start["dateTime"])
        return dt.strftime("%H:%M")
    return "All day"


def event_start_date(event: dict) -> Optional[datetime]:
    """Return the start as a datetime (None if unparseable)."""
    start = event.get("start", {})
    if "dateTime" in start:
        return datetime.fromisoformat(start["dateTime"])
    if "date" in start:
        return datetime.fromisoformat(start["date"])
    return None
