"""
widget_event_list.py — Scrollable agenda list (left panel of full window).
"""
from __future__ import annotations

import datetime
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from colour_theme import c
from google_client import (
    GoogleClient, event_color, event_start_date, event_start_display,
)


def _event_time_display(event: dict) -> str:
    """Return 'HH:MM – HH:MM' for timed events, 'All day' for all-day events."""
    start_str = event_start_display(event)
    if start_str == "All day":
        return "All day"
    end_info = event.get("end", {})
    if "dateTime" in end_info:
        end_dt = datetime.datetime.fromisoformat(end_info["dateTime"])
        return f"{start_str} – {end_dt.strftime('%H:%M')}"
    return start_str


def _date_header_text(d: datetime.date, is_today: bool) -> str:
    day_abbr  = d.strftime("%a")   # "Mon"
    month_abbr = d.strftime("%b")  # "Apr"
    if is_today:
        return f"Today — {day_abbr} {d.day} {month_abbr}"
    return f"{day_abbr} {d.day} {month_abbr}"


# ── Event row ─────────────────────────────────────────────────────────────────

class _EventRow(QWidget):
    clicked = pyqtSignal(dict)

    def __init__(self, event: dict, parent=None):
        super().__init__(parent)
        self._event   = event
        self._selected = False
        self._build()
        self._refresh_style()

    def set_selected(self, selected: bool):
        self._selected = selected
        self._refresh_style()

    def mousePressEvent(self, event):
        self.clicked.emit(self._event)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        if not self._selected:
            self.setStyleSheet(
                f"QWidget#eventRow {{ background: {c('row_hover_bg')}; border-left: 3px solid transparent; }}"
            )
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._refresh_style()
        super().leaveEvent(event)

    def _refresh_style(self):
        if self._selected:
            self.setStyleSheet(
                f"QWidget#eventRow {{ background: {c('row_selected_bg')}; border-left: 3px solid {c('accent')}; }}"
            )
            self._chevron.setStyleSheet(f"color: {c('accent')}; background: transparent; font-size: 14px;")
        else:
            self.setStyleSheet(
                "QWidget#eventRow { background: transparent; border-left: 3px solid transparent; }"
            )
            self._chevron.setStyleSheet(f"color: {c('scroll_handle')}; background: transparent; font-size: 14px;")

    def _build(self):
        self.setObjectName("eventRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(11, 8, 14, 8)  # 11px left (14px - 3px for border)
        layout.setSpacing(10)

        # Color dot
        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background: {event_color(self._event)}; border-radius: 4px;")
        layout.addWidget(dot)

        # Info: title + time stacked
        info = QWidget()
        info.setStyleSheet("background: transparent;")
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        title_raw = self._event.get("summary") or "(No title)"
        title_lbl = QLabel(title_raw)
        title_lbl.setStyleSheet(f"font-size: 13px; color: {c('text')}; background: transparent;")
        title_lbl.setTextFormat(Qt.TextFormat.PlainText)
        info_layout.addWidget(title_lbl)

        time_lbl = QLabel(_event_time_display(self._event))
        time_lbl.setStyleSheet(f"font-size: 11px; color: {c('dim')}; background: transparent;")
        info_layout.addWidget(time_lbl)

        layout.addWidget(info, 1)

        # Chevron
        self._chevron = QLabel("›")
        layout.addWidget(self._chevron)


# ── Date group header ─────────────────────────────────────────────────────────

class _DateGroupHeader(QWidget):
    def __init__(self, text: str, is_today: bool, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 5)
        layout.setSpacing(0)

        lbl = QLabel(text.upper())
        color = c("accent") if is_today else c("dim")
        lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 600; color: {color}; background: transparent;"
        )
        layout.addWidget(lbl)


# ── Event list widget ─────────────────────────────────────────────────────────

class EventListWidget(QWidget):
    event_selected    = pyqtSignal(dict)
    today_requested = pyqtSignal()
    new_event_requested = pyqtSignal()
    edit_requested = pyqtSignal(dict)
    delete_requested = pyqtSignal(dict)

    def __init__(self, google_client: GoogleClient, parent=None):
        super().__init__(parent)
        self._client        = google_client
        self._rows: list[_EventRow] = []
        self._selected_evt: Optional[dict] = None
        self._active_filter_date: Optional[datetime.date] = None

        self._build_ui()
        self._apply_style()

    # ── Public ────────────────────────────────────────────────────────────────

    @property
    def selected_event(self) -> Optional[dict]:
        return self._selected_evt

    def set_filter_date(self, filter_date: Optional[datetime.date]) -> None:
        """Update toolbar title to reflect active date filtering."""
        self._active_filter_date = filter_date
        if filter_date is None:
            self._title_lbl.setText("AGENDA")
            return
        self._title_lbl.setText(f"AGENDA · {filter_date.strftime('%a %d %b')}")

    def load_events(self, events: list[dict]):
        """Group events by date and populate the scroll area."""
        # Clear existing rows
        self._rows.clear()
        self._selected_evt = None
        self._edit_btn.setVisible(False)
        self._delete_btn.setVisible(False)

        # Remove all items from scroll layout
        while self._scroll_layout.count():
            item = self._scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Group by date
        today = datetime.date.today()
        groups: dict[datetime.date, list[dict]] = {}
        for evt in events:
            dt = event_start_date(evt)
            if dt is not None:
                d = dt.date()
                groups.setdefault(d, []).append(evt)

        for d in sorted(groups.keys()):
            is_today = d == today
            header = _DateGroupHeader(_date_header_text(d, is_today), is_today)
            self._scroll_layout.addWidget(header)

            for evt in groups[d]:
                row = _EventRow(evt)
                row.clicked.connect(self._on_row_clicked)
                self._rows.append(row)
                self._scroll_layout.addWidget(row)

        if not groups:
            empty_text = "No events this month" if self._active_filter_date is None else "No events for selected date"
            empty = QLabel(empty_text)
            empty.setStyleSheet(
                f"color: {c('muted')}; font-size: 12px; font-style: italic;"
                f" padding: 16px 14px; background: {c('bg')};"
            )
            self._scroll_layout.addWidget(empty)

        self._scroll_layout.addStretch()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setObjectName("listToolbar")
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(14, 12, 14, 10)
        tl.setSpacing(6)

        self._title_lbl = QLabel("AGENDA")
        self._title_lbl.setObjectName("agendaTitle")
        tl.addWidget(self._title_lbl)
        tl.addStretch()

        # Edit + Delete — hidden until selection
        self._edit_btn = QPushButton("Edit")
        self._edit_btn.setVisible(False)
        self._edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._edit_btn.setStyleSheet(self._action_btn_style())
        self._edit_btn.clicked.connect(self._on_edit)
        tl.addWidget(self._edit_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setVisible(False)
        self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_btn.setStyleSheet(self._delete_btn_style())
        self._delete_btn.clicked.connect(self._on_delete)
        tl.addWidget(self._delete_btn)

        self._today_btn = QPushButton("Today")
        self._today_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._today_btn.setStyleSheet(self._action_btn_style())
        self._today_btn.clicked.connect(self.today_requested)
        tl.addWidget(self._today_btn)

        self._new_btn = QPushButton("＋ New Event")
        self._new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_btn.setStyleSheet(self._new_btn_style())
        self._new_btn.clicked.connect(self.new_event_requested)
        tl.addWidget(self._new_btn)

        main.addWidget(toolbar)

        # Separator
        self._sep = QWidget()
        self._sep.setObjectName("listSep")
        self._sep.setFixedHeight(1)
        main.addWidget(self._sep)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._scroll_content = QWidget()
        self._scroll_content.setObjectName("listScrollContent")
        self._scroll_layout = QVBoxLayout(self._scroll_content)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(0)
        self._scroll.setWidget(self._scroll_content)

        main.addWidget(self._scroll, 1)

    def _apply_style(self):
        self.setStyleSheet(f"""
            QWidget#listToolbar {{
                background: {c("bg")};
                border-bottom: none;
            }}
            QLabel#agendaTitle {{
                font-size: 12px;
                font-weight: 600;
                color: {c("accent")};
                background: transparent;
            }}
            QWidget#listSep {{
                background: {c("border")};
            }}
            QWidget#listScrollContent {{
                background: {c("bg")};
            }}
        """)
        self._scroll.setStyleSheet(f"""
            QScrollArea {{ background: {c("bg")}; border: none; }}
            QScrollBar:vertical {{ width: 4px; background: transparent; }}
            QScrollBar::handle:vertical {{
                background: {c("scroll_handle")}; border-radius: 2px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

    # ── Button styles ─────────────────────────────────────────────────────────

    def _new_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background: {c("agenda_btn_bg")};
                border: 1px solid {c("agenda_btn_border")};
                border-radius: 5px;
                color: {c("accent")};
                font-size: 11px;
                font-weight: 500;
                padding: 5px 11px;
            }}
            QPushButton:hover {{
                background: {c("agenda_btn_bg_hover")};
                border-color: {c("agenda_btn_border_hover")};
            }}
        """

    def _action_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {c("action_btn_border")};
                border-radius: 5px;
                color: {c("dim")};
                font-size: 11px;
                padding: 5px 10px;
            }}
            QPushButton:hover {{
                color: {c("text")};
                border-color: {c("action_btn_border_hover")};
            }}
        """

    def _delete_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {c("danger_btn_border")};
                border-radius: 5px;
                color: {c("danger")};
                font-size: 11px;
                padding: 5px 10px;
            }}
            QPushButton:hover {{
                background: {c("danger_btn_bg_hover")};
                border-color: {c("danger_btn_border_hover")};
            }}
        """

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_row_clicked(self, event: dict):
        # Deselect all
        for row in self._rows:
            row.set_selected(False)

        # Select the clicked row
        for row in self._rows:
            if row._event is event:
                row.set_selected(True)
                break

        self._selected_evt = event
        self._edit_btn.setVisible(True)
        self._delete_btn.setVisible(True)
        self.event_selected.emit(event)

    def _on_edit(self):
        if self._selected_evt is not None:
            self.edit_requested.emit(self._selected_evt)

    def _on_delete(self):
        if self._selected_evt is not None:
            self.delete_requested.emit(self._selected_evt)

    def apply_theme(self):
        self._today_btn.setStyleSheet(self._action_btn_style())
        self._new_btn.setStyleSheet(self._new_btn_style())
        self._edit_btn.setStyleSheet(self._action_btn_style())
        self._delete_btn.setStyleSheet(self._delete_btn_style())
        self._apply_style()
        for row in self._rows:
            row._refresh_style()
