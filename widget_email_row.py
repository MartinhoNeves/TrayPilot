"""
widget_email_row.py — Shared single-row widget for unread Gmail messages.

Used in both the popup flyout (INBOX-07) and the Emails tab (INBOX-08).
Each row shows: optional checkbox · unread dot · sender (bold) · subject · date.
Emits clicked(msg_dict) when the content area is clicked (not the checkbox).
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QWidget

from colour_theme import c


class EmailRow(QWidget):
    """
    Compact single-line row for one unread message.
    Emits clicked(message: dict) on left-click outside the checkbox.
    When selectable=True, shows a checkbox; selection_changed fires when it toggles.
    """
    clicked = pyqtSignal(dict)
    selection_changed = pyqtSignal()

    ROW_HEIGHT = 38

    def __init__(self, message: dict, parent=None, *, selectable: bool = False):
        super().__init__(parent)
        self._message = message
        self._hovered = False
        self._selectable = selectable
        self._checkbox: QCheckBox | None = None

        self.setObjectName("emailRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(self.ROW_HEIGHT)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(8)

        if selectable:
            self._checkbox = QCheckBox()
            self._checkbox.setObjectName("emailRowChk")
            self._checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
            self._checkbox.setFixedWidth(22)
            self._checkbox.stateChanged.connect(lambda _s: self.selection_changed.emit())
            lay.addWidget(self._checkbox)

        # Unread dot
        self._dot = QLabel()
        self._dot.setFixedSize(7, 7)
        lay.addWidget(self._dot)

        # Sender (bold, fixed width so subjects align)
        sender_text = _truncate(message.get("from", ""), 20)
        self._sender_lbl = QLabel(sender_text)
        self._sender_lbl.setFixedWidth(128)
        lay.addWidget(self._sender_lbl)

        # Subject (fills remaining space, elides at right)
        self._subject_lbl = QLabel(message.get("subject", "(No subject)"))
        self._subject_lbl.setMinimumWidth(0)
        lay.addWidget(self._subject_lbl, 1)

        # Date (right-aligned, compact)
        self._date_lbl = QLabel(message.get("date_display", ""))
        self._date_lbl.setFixedWidth(40)
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self._date_lbl)

        self.apply_theme()

    @property
    def message(self) -> dict:
        return self._message

    def is_checked(self) -> bool:
        return bool(self._checkbox and self._checkbox.isChecked())

    def set_checked(self, on: bool) -> None:
        if self._checkbox:
            self._checkbox.setChecked(on)

    def _is_under_checkbox(self, pos) -> bool:
        if self._checkbox is None:
            return False
        w = self.childAt(pos)
        while w:
            if w is self._checkbox:
                return True
            w = w.parentWidget()
        return False

    # ── Interaction ───────────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and not self._is_under_checkbox(event.pos()):
            self.clicked.emit(self._message)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self._hovered = True
        self._apply_bg()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._apply_bg()
        super().leaveEvent(event)

    # ── Theme ──────────────────────────────────────────────────────────────────

    def apply_theme(self):
        if self._checkbox:
            self._checkbox.setStyleSheet(f"""
                QCheckBox#emailRowChk {{
                    background: transparent;
                    spacing: 0;
                }}
                QCheckBox#emailRowChk::indicator {{
                    width: 16px;
                    height: 16px;
                    border-radius: 3px;
                    border: 1px solid {c('action_btn_border')};
                    background: {c('titlebar')};
                }}
                QCheckBox#emailRowChk::indicator:checked {{
                    background: {c('accent')};
                    border-color: {c('accent')};
                }}
            """)
        self._dot.setStyleSheet(
            f"background: {c('accent')}; border-radius: 3px;"
        )
        self._sender_lbl.setStyleSheet(
            f"color: {c('text')}; font-size: 12px; font-weight: 600; background: transparent;"
        )
        self._subject_lbl.setStyleSheet(
            f"color: {c('dim')}; font-size: 12px; background: transparent;"
        )
        self._date_lbl.setStyleSheet(
            f"color: {c('dim')}; font-size: 11px; background: transparent;"
        )
        self._apply_bg()

    def _apply_bg(self):
        if self._hovered:
            self.setStyleSheet(
                f"QWidget#emailRow {{ background: {c('row_hover_bg')};"
                f" border-left: 3px solid {c('accent')}; }}"
            )
        else:
            self.setStyleSheet(
                "QWidget#emailRow { background: transparent;"
                " border-left: 3px solid transparent; }"
            )


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"
