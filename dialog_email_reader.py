"""
dialog_email_reader.py — Email reader dialog (INBOX-09).

Shows From / Subject / Date header and plain-text body in a QTextBrowser.
Automatically marks the message as read on open.
Supports Trash action (trashes + closes) and Close button.
Body is fetched asynchronously so the dialog appears immediately.
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QTextBrowser, QVBoxLayout, QWidget,
)

from colour_theme import c

if TYPE_CHECKING:
    from gmail_client import GmailClient


class EmailReaderDialog(QDialog):
    """
    Single-message reader dialog.

    Opens, marks as read, and fetches body — all non-blocking.
    Emits trashed(msg_id) when the user trashes the message.
    """
    trashed = pyqtSignal(str)

    def __init__(self, message: dict, gmail_client: "GmailClient", parent=None):
        super().__init__(parent)
        self._message = message
        self._gmail = gmail_client
        self._msg_id: str = message.get("id", "")

        self.setWindowTitle("Email")
        self.setMinimumSize(580, 480)
        self.resize(640, 540)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)

        self._build_ui()
        self._apply_theme()

        # Mark as read immediately — local state update is instant, API call is background
        if self._msg_id:
            self._gmail.mark_as_read(self._msg_id)

        # Fetch body in background; show snippet as placeholder meanwhile
        QTimer.singleShot(0, self._start_body_fetch)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 16)
        root.setSpacing(0)

        # Subject
        self._subject_lbl = QLabel(self._message.get("subject", "(No subject)"))
        self._subject_lbl.setObjectName("readerSubject")
        self._subject_lbl.setWordWrap(True)
        root.addWidget(self._subject_lbl)
        root.addSpacing(10)

        self._sep1 = _Sep()
        root.addWidget(self._sep1)
        root.addSpacing(8)

        # From / Date
        meta = QWidget()
        ml = QVBoxLayout(meta)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(3)
        from_raw = self._message.get("from_raw") or self._message.get("from", "")
        self._from_lbl = QLabel(f"From:  {from_raw}")
        self._from_lbl.setObjectName("readerMeta")
        self._date_lbl = QLabel(f"Date:  {self._message.get('date', '')}")
        self._date_lbl.setObjectName("readerMeta")
        ml.addWidget(self._from_lbl)
        ml.addWidget(self._date_lbl)
        root.addWidget(meta)
        root.addSpacing(8)

        self._sep2 = _Sep()
        root.addWidget(self._sep2)
        root.addSpacing(10)

        # Body
        self._body = QTextBrowser()
        self._body.setObjectName("readerBody")
        self._body.setOpenExternalLinks(True)
        self._body.setReadOnly(True)
        self._body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        snippet = self._message.get("snippet", "")
        self._body.setText(snippet if snippet else "Loading…")
        root.addWidget(self._body, 1)

        root.addSpacing(14)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        self._trash_btn = QPushButton("🗑  Trash")
        self._trash_btn.setObjectName("readerTrashBtn")
        self._trash_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._trash_btn.clicked.connect(self._on_trash)
        btn_row.addWidget(self._trash_btn)

        self._open_gmail_btn = QPushButton("Open Gmail ↗")
        self._open_gmail_btn.setObjectName("readerOpenGmailBtn")
        self._open_gmail_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_gmail_btn.clicked.connect(self._on_open_gmail)
        btn_row.addWidget(self._open_gmail_btn)

        self._close_btn = QPushButton("Close")
        self._close_btn.setObjectName("readerCloseBtn")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._close_btn)

        root.addLayout(btn_row)

    def _apply_theme(self):
        self.setStyleSheet(f"""
            QDialog {{
                background: {c('bg')};
                color: {c('text')};
                font-family: 'Segoe UI', sans-serif;
            }}
            QLabel#readerSubject {{
                font-size: 15px;
                font-weight: 700;
                color: {c('text')};
                background: transparent;
            }}
            QLabel#readerMeta {{
                font-size: 11px;
                color: {c('dim')};
                background: transparent;
            }}
            QTextBrowser#readerBody {{
                background: {c('titlebar')};
                color: {c('text')};
                border: 1px solid {c('border')};
                border-radius: 6px;
                padding: 10px;
                font-size: 13px;
                font-family: 'Segoe UI', sans-serif;
            }}
            QPushButton#readerTrashBtn {{
                background: {c('danger_btn_bg_hover')};
                border: 1px solid {c('danger_btn_border')};
                border-radius: 6px;
                color: {c('danger')};
                font-size: 12px;
                padding: 6px 16px;
            }}
            QPushButton#readerTrashBtn:hover {{
                border-color: {c('danger_btn_border_hover')};
            }}
            QPushButton#readerCloseBtn {{
                background: {c('agenda_btn_bg')};
                border: 1px solid {c('agenda_btn_border')};
                border-radius: 6px;
                color: {c('accent')};
                font-size: 12px;
                padding: 6px 16px;
            }}
            QPushButton#readerCloseBtn:hover {{
                background: {c('agenda_btn_bg_hover')};
                border-color: {c('agenda_btn_border_hover')};
            }}
            QPushButton#readerOpenGmailBtn {{
                background: {c('agenda_btn_bg')};
                border: 1px solid {c('agenda_btn_border')};
                border-radius: 6px;
                color: {c('accent')};
                font-size: 12px;
                padding: 6px 16px;
            }}
            QPushButton#readerOpenGmailBtn:hover {{
                background: {c('agenda_btn_bg_hover')};
                border-color: {c('agenda_btn_border_hover')};
            }}
        """)
        self._sep1.refresh_style()
        self._sep2.refresh_style()

    # ── Actions ───────────────────────────────────────────────────────────────

    def _start_body_fetch(self):
        if not self._msg_id:
            return
        threading.Thread(
            target=self._fetch_body_worker, args=(self._msg_id,), daemon=True
        ).start()

    def _fetch_body_worker(self, msg_id: str):
        body = self._gmail.get_message_body(msg_id)
        QTimer.singleShot(0, lambda: self._set_body(body))

    def _set_body(self, body: str):
        if body:
            self._body.setText(body)

    def _on_trash(self):
        if self._msg_id:
            self._gmail.trash_message(self._msg_id)
            self.trashed.emit(self._msg_id)
        self.accept()

    def _on_open_gmail(self):
        msg_url = "https://mail.google.com/mail/u/0/#inbox"
        if self._msg_id:
            msg_url = f"https://mail.google.com/mail/u/0/#inbox/{self._msg_id}"
        QDesktopServices.openUrl(QUrl(msg_url))


class _Sep(QWidget):
    """Thin horizontal separator that re-styles with the current theme."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(1)
        self.refresh_style()

    def refresh_style(self):
        self.setStyleSheet(f"background: {c('border')};")
