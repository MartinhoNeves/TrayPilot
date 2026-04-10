"""
gmail_client.py — Gmail inbox service (read, mark-as-read, trash).

Fully UI-independent: no widgets, no dialogs.
All Gmail API calls happen here.  Signals carry only metadata — no raw
auth tokens or full email addresses are ever logged (MAIL-09 / INBOX security).

Public interface
----------------
    start_polling(interval_minutes)  — begin background polling
    stop_polling()                   — stop the timer
    poll_now()                       — immediate one-shot poll
    get_message_body(msg_id) -> str  — fetch plain-text body (blocking, call from thread)
    trash_message(msg_id)            — move to trash; updates local state immediately
    mark_as_read(msg_id)             — removes UNREAD label; updates local state immediately
    is_ready      (property)         — True once Gmail service is built
    needs_reauth  (property)         — True if token lacks gmail.modify scope
    last_unread_count (property)     — most recent polled total unread count (-1 = unknown)
    messages      (property)         — copy of the current in-memory message list

Signals
-------
    unread_count_changed(int)    — total unread count changed
    new_mail_detected(int)       — count increased vs. previous reading
    messages_changed(list)       — message list replaced (list[dict] with id/from/subject/date/snippet)
    scope_upgrade_required()     — token lacks required scope; UI should offer re-auth
"""
from __future__ import annotations

import base64
import email.utils
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

if TYPE_CHECKING:
    from google_client import GoogleClient

# Must match the scope in google_client._SCOPES
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.modify"

_DEFAULT_POLL_INTERVAL_MINUTES = 5
_MAX_MESSAGES = 20  # max unread messages fetched per poll cycle


class GmailClient(QObject):
    unread_count_changed   = pyqtSignal(int)
    new_mail_detected      = pyqtSignal(int)
    messages_changed       = pyqtSignal(list)    # list[dict]
    scope_upgrade_required = pyqtSignal()

    def __init__(self, google_client: "GoogleClient", parent=None):
        super().__init__(parent)
        self._google_client = google_client
        self._service = None
        self._api_lock = threading.Lock()
        self._messages: list[dict] = []
        self._messages_lock = threading.Lock()
        self._last_unread_count: int = -1   # -1 = not yet fetched
        self._needs_reauth: bool = False
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_in_thread)
        self._google_client.ready.connect(self._on_google_ready)

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def is_ready(self) -> bool:
        return self._service is not None

    @property
    def needs_reauth(self) -> bool:
        return self._needs_reauth

    @property
    def last_unread_count(self) -> int:
        return self._last_unread_count

    @property
    def messages(self) -> list[dict]:
        with self._messages_lock:
            return list(self._messages)

    # ── Polling control ───────────────────────────────────────────────────────

    def start_polling(self, interval_minutes: int = _DEFAULT_POLL_INTERVAL_MINUTES) -> None:
        """Start background polling at the given interval. Kicks off an immediate poll."""
        if not self._service:
            return
        interval_ms = max(1, interval_minutes) * 60 * 1000
        self._poll_timer.start(interval_ms)
        QTimer.singleShot(0, self._poll_in_thread)

    def stop_polling(self) -> None:
        self._poll_timer.stop()

    def poll_now(self) -> None:
        """Immediate one-shot poll (e.g. user clicks Refresh)."""
        if self._service:
            self._poll_in_thread()

    # ── Message actions (INBOX-03, INBOX-04, INBOX-05) ────────────────────────

    def get_message_body(self, msg_id: str) -> str:
        """
        Fetch the plain-text body of a message.
        Falls back to snippet if no plain-text part exists.
        Blocks until the API responds — call from a background thread.
        """
        if self._service is None:
            return ""
        try:
            with self._api_lock:
                result = (
                    self._service.users()
                    .messages()
                    .get(userId="me", id=msg_id, format="full")
                    .execute()
                )
            body = _extract_plain_text(result.get("payload", {}))
            return body if body else result.get("snippet", "")
        except Exception:
            return ""

    def trash_message(self, msg_id: str) -> None:
        """
        Move message to Gmail trash.
        INBOX-10: local state updated immediately; API call runs in background.
        """
        self._remove_message_locally(msg_id)
        threading.Thread(target=self._api_trash, args=(msg_id,), daemon=True).start()

    def mark_as_read(self, msg_id: str) -> None:
        """
        Remove UNREAD label from a message.
        INBOX-10: local state updated immediately; API call runs in background.
        """
        self._remove_message_locally(msg_id)
        threading.Thread(target=self._api_mark_read, args=(msg_id,), daemon=True).start()

    # ── Internal: Google auth wiring ──────────────────────────────────────────

    def _on_google_ready(self) -> None:
        from settings import get_mail_awareness_enabled, get_mail_poll_interval_minutes

        if not get_mail_awareness_enabled():
            return

        creds = self._google_client.credentials
        if creds is None:
            return

        # Detect scope mismatch (e.g. old token only has gmail.readonly)
        if creds.scopes is not None and GMAIL_SCOPE not in creds.scopes:
            self._needs_reauth = True
            self.scope_upgrade_required.emit()
            return

        try:
            self._service = build(
                "gmail", "v1",
                credentials=creds,
                cache_discovery=False,
            )
        except Exception:
            return  # Non-fatal — Gmail features won't function

        self.start_polling(get_mail_poll_interval_minutes())

    # ── Internal: polling ─────────────────────────────────────────────────────

    def _poll_in_thread(self) -> None:
        threading.Thread(target=self._fetch_data, daemon=True).start()

    def _fetch_data(self) -> None:
        """
        Background thread: fetch accurate unread count + metadata for recent
        unread messages in exactly 3 network round-trips regardless of inbox size:
          1. labels.get(INBOX)          → accurate total unread count
          2. messages.list(is:unread)   → up to _MAX_MESSAGES IDs
          3. batch messages.get (×N)    → all metadata in one multipart HTTP POST
        """
        if self._service is None:
            return
        try:
            # Step 1 + 2: count and ID list (sequential, fast)
            with self._api_lock:
                label_res = (
                    self._service.users()
                    .labels()
                    .get(userId="me", id="INBOX")
                    .execute()
                )
                list_res = (
                    self._service.users()
                    .messages()
                    .list(userId="me", q="is:unread in:inbox", maxResults=_MAX_MESSAGES)
                    .execute()
                )
            count: int = int(label_res.get("messagesUnread", 0))
            items = list_res.get("messages", [])

            # Step 3: batch-fetch all metadata in ONE HTTP multipart request
            batch_details: dict[str, dict] = {}

            def _on_result(request_id, response, exception):
                if exception is None and response is not None:
                    batch_details[request_id] = response

            if items:
                batch = self._service.new_batch_http_request(callback=_on_result)
                for item in items:
                    batch.add(
                        self._service.users()
                        .messages()
                        .get(
                            userId="me",
                            id=item["id"],
                            format="metadata",
                            metadataHeaders=["From", "Subject", "Date"],
                        ),
                        request_id=item["id"],
                    )
                with self._api_lock:
                    batch.execute()

            # Build ordered message list (preserve newest-first order from list_res)
            messages: list[dict] = []
            for item in items:
                detail = batch_details.get(item["id"])
                if detail is None:
                    continue
                hdrs = {
                    h["name"]: h["value"]
                    for h in detail.get("payload", {}).get("headers", [])
                }
                messages.append({
                    "id": item["id"],
                    "from": _parse_sender(hdrs.get("From", "")),
                    "from_raw": hdrs.get("From", ""),
                    "subject": hdrs.get("Subject") or "(No subject)",
                    "date": hdrs.get("Date", ""),
                    "date_display": _format_date(hdrs.get("Date", "")),
                    "snippet": detail.get("snippet", ""),
                })

            with self._messages_lock:
                self._messages = messages

            prev = self._last_unread_count
            self._last_unread_count = count

            if prev != count:
                self.unread_count_changed.emit(count)
            if prev != -1 and count > prev:
                self.new_mail_detected.emit(count)
            self.messages_changed.emit(list(messages))

        except HttpError as exc:
            status = exc.resp.status if exc.resp else 0
            if status in (401, 403):
                self._service = None
                self.stop_polling()
                self._needs_reauth = True
                self.scope_upgrade_required.emit()
        except Exception:
            pass  # Transient network error; retry on next poll

    # ── Internal: instant local state updates (INBOX-10) ─────────────────────

    def _remove_message_locally(self, msg_id: str) -> None:
        with self._messages_lock:
            self._messages = [m for m in self._messages if m["id"] != msg_id]
            snapshot = list(self._messages)
        count = max(0, self._last_unread_count - 1)
        self._last_unread_count = count
        self.messages_changed.emit(snapshot)
        self.unread_count_changed.emit(count)

    # ── Internal: background API calls ───────────────────────────────────────

    def _api_trash(self, msg_id: str) -> None:
        if self._service is None:
            return
        try:
            with self._api_lock:
                self._service.users().messages().trash(
                    userId="me", id=msg_id
                ).execute()
        except Exception:
            pass  # Non-fatal; next poll corrects state

    def _api_mark_read(self, msg_id: str) -> None:
        if self._service is None:
            return
        try:
            with self._api_lock:
                self._service.users().messages().modify(
                    userId="me",
                    id=msg_id,
                    body={"removeLabelIds": ["UNREAD"]},
                ).execute()
        except Exception:
            pass


# ── Module-level helpers ───────────────────────────────────────────────────────

def _extract_plain_text(payload: dict) -> str:
    """Recursively extract and decode plain-text body from a message payload."""
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            try:
                return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
            except Exception:
                return ""
    for part in payload.get("parts", []):
        result = _extract_plain_text(part)
        if result:
            return result
    return ""


def _parse_sender(from_header: str) -> str:
    """Return display name from a From header, or the email address as fallback."""
    if not from_header:
        return "(Unknown)"
    try:
        name, addr = email.utils.parseaddr(from_header)
        display = name.strip() if name.strip() else addr.strip()
        return display or "(Unknown)"
    except Exception:
        return from_header[:40]


def _format_date(date_header: str) -> str:
    """
    Return a compact date string for display in a single-line row:
      - Today: 'HH:MM'
      - This week: day abbreviation ('Mon')
      - Older: 'Apr 10'
    """
    if not date_header:
        return ""
    try:
        dt = email.utils.parsedate_to_datetime(date_header)
        now = datetime.now(timezone.utc)
        dt_utc = dt.astimezone(timezone.utc)
        diff = now - dt_utc
        if diff.days == 0:
            return dt.astimezone().strftime("%H:%M")
        if diff.days < 7:
            return dt.astimezone().strftime("%a")
        return dt.astimezone().strftime("%b %d")
    except Exception:
        return ""
