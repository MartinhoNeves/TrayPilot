"""
widget_email_stub.py — Gmail Inbox tab widget (M12 / INBOX-08).

Displays a live scrollable list of unread Gmail messages using EmailRow.
Click a row to open the EmailReaderDialog. Mail preferences live on the Settings tab.
"""
from __future__ import annotations

import webbrowser
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from colour_theme import c
from widget_email_row import EmailRow

if TYPE_CHECKING:
    from gmail_client import GmailClient

GMAIL_URL = "https://mail.google.com/"


class EmailStubWidget(QWidget):
    """Gmail Inbox panel — live scrollable unread list."""

    def __init__(self, gmail_client: "GmailClient | None" = None, parent=None):
        super().__init__(parent)
        self._gmail = gmail_client
        self._rows: list[EmailRow] = []
        self._build_ui()
        self.apply_theme()

        if self._gmail is not None:
            self._gmail.messages_changed.connect(self._on_messages_changed)
            self._gmail.scope_upgrade_required.connect(self._on_scope_upgrade)
            QTimer.singleShot(0, self._sync_state)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────────
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 12, 14, 10)
        hl.setSpacing(6)
        self._title_lbl = QLabel("INBOX")
        self._title_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        hl.addWidget(self._title_lbl)
        self._count_lbl = QLabel("")
        hl.addWidget(self._count_lbl)
        self._trash_selected_btn = QPushButton("Trash selected")
        self._trash_selected_btn.setObjectName("trashSelectedBtn")
        self._trash_selected_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._trash_selected_btn.setEnabled(False)
        self._trash_selected_btn.clicked.connect(self._on_trash_selected)
        hl.addWidget(self._trash_selected_btn)
        self._open_btn = QPushButton("Open Gmail ↗")
        self._open_btn.setObjectName("openGmailBtn")
        self._open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_btn.clicked.connect(lambda: webbrowser.open(GMAIL_URL))
        hl.addWidget(self._open_btn)
        root.addWidget(header)

        self._sep_top = QWidget()
        self._sep_top.setFixedHeight(1)
        root.addWidget(self._sep_top)

        # ── Scrollable message list ───────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch()
        self._scroll.setWidget(self._list_container)
        root.addWidget(self._scroll, 1)

        # ── Re-auth notice (hidden by default) ────────────────────────────────
        self._reauth_area = QWidget()
        ral = QVBoxLayout(self._reauth_area)
        ral.setContentsMargins(14, 12, 14, 12)
        ral.setSpacing(8)
        self._reauth_lbl = QLabel(
            "Your authorization token does not include Gmail access.\n"
            "Click Re-authorize to grant the required permissions."
        )
        self._reauth_lbl.setWordWrap(True)
        self._reauth_btn = QPushButton("Re-authorize")
        self._reauth_btn.setObjectName("reauthBtn")
        self._reauth_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reauth_btn.clicked.connect(self._on_reauth_clicked)
        ral.addWidget(self._reauth_lbl)
        ral.addWidget(self._reauth_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self._reauth_area.setVisible(False)
        root.addWidget(self._reauth_area)

    # ── Message list population ───────────────────────────────────────────────

    def _populate_list(self, messages: list[dict]):
        """Rebuild the email row list from a fresh message list."""
        # Remove existing rows (keep the trailing stretch)
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._rows = []

        if not messages:
            empty = QLabel("No unread messages.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color: {c('muted')}; font-size: 12px; font-style: italic; padding: 24px;"
            )
            self._list_layout.insertWidget(0, empty)
            self._count_lbl.setText("")
            self._refresh_trash_selected_state()
            return

        for i, msg in enumerate(messages):
            row = EmailRow(msg, self, selectable=True)
            row.clicked.connect(self._on_row_clicked)
            row.selection_changed.connect(self._refresh_trash_selected_state)
            self._list_layout.insertWidget(i, row)
            self._rows.append(row)

        noun = "message" if len(messages) == 1 else "messages"
        self._count_lbl.setText(f"{len(messages)} unread {noun}")
        self._refresh_trash_selected_state()

    # ── State synchronization ─────────────────────────────────────────────────

    def _sync_state(self):
        if self._gmail is None:
            self._show_placeholder("Gmail awareness not available.")
            return
        if self._gmail.needs_reauth:
            self._on_scope_upgrade()
            return
        msgs = self._gmail.messages
        if not msgs and self._gmail.last_unread_count == -1:
            self._show_placeholder("Checking for new mail…")
        else:
            self._populate_list(msgs)

    def _show_placeholder(self, text: str):
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._rows = []
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"color: {c('dim')}; font-size: 12px; font-style: italic; padding: 24px;"
        )
        self._list_layout.insertWidget(0, lbl)
        self._count_lbl.setText("")
        self._refresh_trash_selected_state()

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_messages_changed(self, messages: list):
        self._reauth_area.setVisible(False)
        self._populate_list(messages)

    def _on_scope_upgrade(self):
        self._show_placeholder("")
        self._reauth_area.setVisible(True)
        self._count_lbl.setText("")

    def _on_row_clicked(self, message: dict):
        from dialog_email_reader import EmailReaderDialog
        if self._gmail is None:
            return
        dlg = EmailReaderDialog(message, self._gmail, parent=self.window())
        dlg.exec()

    def _refresh_trash_selected_state(self) -> None:
        if not self._rows:
            self._trash_selected_btn.setEnabled(False)
            return
        self._trash_selected_btn.setEnabled(any(r.is_checked() for r in self._rows))

    def _on_trash_selected(self) -> None:
        if self._gmail is None:
            return
        ids = [r.message["id"] for r in self._rows if r.is_checked()]
        if not ids:
            return
        n = len(ids)
        noun = "this message" if n == 1 else f"these {n} messages"
        reply = QMessageBox.question(
            self.window(),
            "Trash messages",
            f"Move {noun} to Gmail trash?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for mid in ids:
            self._gmail.trash_message(mid)

    def _on_reauth_clicked(self):
        if self._gmail is not None:
            self._gmail._google_client.revoke_and_reauth()
            self._reauth_area.setVisible(False)
            self._show_placeholder("Authorizing…")

    # ── Theme ──────────────────────────────────────────────────────────────────

    def apply_theme(self):
        self._title_lbl.setStyleSheet(
            f"color: {c('accent')}; font-size: 12px; font-weight: 600;"
        )
        self._count_lbl.setStyleSheet(
            f"color: {c('dim')}; font-size: 11px;"
        )
        self._sep_top.setStyleSheet(f"background: {c('border')};")
        self._reauth_lbl.setStyleSheet(f"color: {c('danger')}; font-size: 12px;")
        self._scroll.setStyleSheet(f"""
            QScrollArea {{ background: {c('bg')}; border: none; }}
            QScrollBar:vertical {{ width: 4px; background: transparent; }}
            QScrollBar::handle:vertical {{
                background: {c('scroll_handle')}; border-radius: 2px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        self._list_container.setStyleSheet(f"background: {c('bg')};")
        self._trash_selected_btn.setStyleSheet(f"""
            QPushButton#trashSelectedBtn {{
                background: {c('danger_btn_bg_hover')};
                border: 1px solid {c('danger_btn_border')};
                border-radius: 6px;
                color: {c('danger')};
                font-size: 12px;
                padding: 4px 10px;
            }}
            QPushButton#trashSelectedBtn:hover:enabled {{
                border-color: {c('danger_btn_border_hover')};
            }}
            QPushButton#trashSelectedBtn:disabled {{
                background: {c('titlebar')};
                color: {c('muted')};
                border-color: {c('border')};
            }}
        """)
        self._open_btn.setStyleSheet(f"""
            QPushButton#openGmailBtn {{
                background: {c('agenda_btn_bg')};
                border: 1px solid {c('agenda_btn_border')};
                border-radius: 6px;
                color: {c('accent')};
                font-size: 12px;
                padding: 4px 10px;
            }}
            QPushButton#openGmailBtn:hover {{
                background: {c('agenda_btn_bg_hover')};
                border-color: {c('agenda_btn_border_hover')};
            }}
        """)
        self._reauth_btn.setStyleSheet(f"""
            QPushButton#reauthBtn {{
                background: {c('danger_btn_bg_hover')};
                border: 1px solid {c('danger_btn_border')};
                border-radius: 6px;
                color: {c('danger')};
                font-size: 12px;
                padding: 5px 10px;
            }}
            QPushButton#reauthBtn:hover {{
                border-color: {c('danger_btn_border_hover')};
            }}
        """)
        for row in self._rows:
            row.apply_theme()
