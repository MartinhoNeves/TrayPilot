"""
panel_event_form.py — Slide-in add/edit event form panel.
"""
from __future__ import annotations

import datetime

from PyQt6.QtCore import QDate, QEasingCurve, QPropertyAnimation, QTime, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QTimeEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from colour_theme import c
from google_client import GOOGLE_COLORS
FORM_WIDTH = 280
ANIMATION_MS = 250

COLOR_OPTIONS = [
    ("1", "Lavender"),
    ("2", "Sage"),
    ("3", "Grape"),
    ("4", "Flamingo"),
    ("5", "Banana"),
    ("6", "Tangerine"),
    ("7", "Peacock"),
    ("8", "Graphite"),
    ("9", "Blueberry"),
    ("10", "Tomato (Urgent)"),
    ("11", "Basil"),
]

RECURRENCE_OPTIONS = [
    ("none", "No recurrence"),
    ("daily", "Daily"),
    ("monthly", "Monthly"),
    ("yearly", "Yearly"),
]

REMINDER_OPTIONS = [
    ("default", "Default"),
    ("none", "None"),
    ("popup", "Notification"),
    ("email", "Email"),
]


class EventFormPanel(QWidget):
    submit_requested = pyqtSignal(object, dict)
    cancel_requested = pyqtSignal()
    width_changed = pyqtSignal(int)

    def __init__(self, google_client, parent=None):
        super().__init__(parent)
        self._client = google_client
        self._editing_event_id: str | None = None
        self._open_width = FORM_WIDTH
        self._animation = QPropertyAnimation(self, b"maximumWidth", self)
        self._animation.setDuration(ANIMATION_MS)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hide_after_anim = False

        self.setMinimumWidth(0)
        self.setMaximumWidth(0)
        self.setVisible(False)
        self._build_ui()
        self.apply_theme()
        self._animation.finished.connect(self._on_animation_finished)
        self._animation.valueChanged.connect(self._on_animation_value_changed)

    def open_for_new(self, when: datetime.date, width: int | None = None) -> None:
        if width is not None:
            self._open_width = max(FORM_WIDTH, int(width))
        self._editing_event_id = None
        self._title_input.setText("")
        self._date_input.setDate(QDate(when.year, when.month, when.day))
        self._start_input.setTime(QTime(9, 0))
        self._end_input.setTime(QTime(10, 0))
        self._description_input.setPlainText("")
        self._set_color_id("9")
        self._set_recurrence("none")
        self._set_reminder("popup", 10)
        self._error_lbl.setText("")
        self._heading_lbl.setText("New event")
        self._save_btn.setText("Save")
        self._animate_to(self._open_width, hide_after=False)

    def open_for_edit(self, event: dict, width: int | None = None) -> None:
        if width is not None:
            self._open_width = max(FORM_WIDTH, int(width))
        self._editing_event_id = event.get("id")
        self._title_input.setText(event.get("summary") or "")
        self._description_input.setPlainText(event.get("description") or "")
        self._set_color_id(event.get("colorId") or "9")
        self._set_recurrence(self._read_recurrence_mode(event))
        self._set_reminder_from_event(event)

        start = event.get("start", {})
        end = event.get("end", {})
        if "dateTime" in start:
            start_dt = datetime.datetime.fromisoformat(start["dateTime"])
            self._date_input.setDate(QDate(start_dt.year, start_dt.month, start_dt.day))
            self._start_input.setTime(QTime(start_dt.hour, start_dt.minute))
        elif "date" in start:
            start_d = datetime.date.fromisoformat(start["date"])
            self._date_input.setDate(QDate(start_d.year, start_d.month, start_d.day))
            self._start_input.setTime(QTime(9, 0))
        else:
            today = datetime.date.today()
            self._date_input.setDate(QDate(today.year, today.month, today.day))
            self._start_input.setTime(QTime(9, 0))

        if "dateTime" in end:
            end_dt = datetime.datetime.fromisoformat(end["dateTime"])
            self._end_input.setTime(QTime(end_dt.hour, end_dt.minute))
        else:
            self._end_input.setTime(QTime(10, 0))

        self._error_lbl.setText("")
        self._heading_lbl.setText("Edit event")
        self._save_btn.setText("Save")
        self._animate_to(self._open_width, hide_after=False)

    def set_open_width(self, width: int) -> None:
        self._open_width = max(FORM_WIDTH, int(width))
        if self.isVisible() and self.maximumWidth() > 0:
            self.setMaximumWidth(self._open_width)

    def close_panel(self) -> None:
        self._error_lbl.setText("")
        self._animate_to(0, hide_after=True)

    def show_error(self, message: str) -> None:
        self._error_lbl.setText(message)

    def apply_theme(self):
        self.setStyleSheet(
            f"""
            QWidget#eventFormPanel {{
                background: {c("titlebar")};
                border-left: 1px solid {c("border")};
            }}
            QLabel#formHeading {{
                color: {c("accent")};
                font-size: 12px;
                font-weight: 600;
                padding: 2px 0 6px 0;
            }}
            QLabel#formError {{
                color: {c("danger")};
                font-size: 11px;
                padding-top: 3px;
            }}
            QLabel#formField {{
                color: {c("dim")};
                font-size: 11px;
            }}
            QLineEdit, QDateEdit, QTimeEdit, QComboBox, QSpinBox, QTextEdit {{
                background: {c("bg")};
                color: {c("text")};
                border: 1px solid {c("action_btn_border")};
                border-radius: 4px;
                padding: 5px;
                font-size: 11px;
            }}
            QTimeEdit, QSpinBox {{
                border-top-right-radius: 0;
                border-bottom-right-radius: 0;
            }}
            QLineEdit:focus, QDateEdit:focus, QTimeEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {{
                border: 1px solid {c("accent")};
            }}
            QComboBox QAbstractItemView {{
                background: {c("titlebar")};
                color: {c("text")};
                border: 1px solid {c("border")};
                selection-background-color: {c("accent")};
            }}
            QPushButton#saveBtn {{
                background: {c("agenda_btn_bg")};
                color: {c("accent")};
                border: 1px solid {c("agenda_btn_border")};
                border-radius: 5px;
                padding: 5px 10px;
            }}
            QPushButton#saveBtn:hover {{
                background: {c("agenda_btn_bg_hover")};
                border-color: {c("agenda_btn_border_hover")};
            }}
            QPushButton#cancelBtn {{
                background: transparent;
                color: {c("dim")};
                border: 1px solid {c("action_btn_border")};
                border-radius: 5px;
                padding: 5px 10px;
            }}
            QPushButton#cancelBtn:hover {{
                color: {c("text")};
                border-color: {c("action_btn_border_hover")};
            }}
            """
        )
        self._apply_color_combo_style()
        style = self._spin_btn_style()
        for btn in getattr(self, "_spin_btns", []):
            btn.setStyleSheet(style)

    def _build_ui(self):
        self.setObjectName("eventFormPanel")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        self._heading_lbl = QLabel("New event")
        self._heading_lbl.setObjectName("formHeading")
        outer.addWidget(self._heading_lbl)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)

        self._title_input = QLineEdit()
        self._title_input.setPlaceholderText("Event title")
        form.addRow(self._field_label("Title"), self._title_input)

        self._date_input = QDateEdit()
        self._date_input.setCalendarPopup(True)
        today = datetime.date.today()
        self._date_input.setDate(QDate(today.year, today.month, today.day))
        self._date_input.setDisplayFormat("ddd dd MMM yyyy")
        form.addRow(self._field_label("Date"), self._date_input)

        time_row = QWidget()
        time_layout = QHBoxLayout(time_row)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(6)
        self._start_input = QTimeEdit()
        self._start_input.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._start_input.setDisplayFormat("HH:mm")
        self._start_input.setTime(QTime(9, 0))
        self._end_input = QTimeEdit()
        self._end_input.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._end_input.setDisplayFormat("HH:mm")
        self._end_input.setTime(QTime(10, 0))
        time_layout.addLayout(self._wrap_spin(self._start_input))
        time_layout.addLayout(self._wrap_spin(self._end_input))
        form.addRow(self._field_label("Start / End"), time_row)

        self._color_input = QComboBox()
        for color_id, label in COLOR_OPTIONS:
            self._color_input.addItem(self._color_item_icon(color_id), label, color_id)
        self._color_input.currentIndexChanged.connect(self._apply_color_combo_style)
        form.addRow(self._field_label("Colour"), self._color_input)

        self._recurrence_input = QComboBox()
        for key, label in RECURRENCE_OPTIONS:
            self._recurrence_input.addItem(label, key)
        form.addRow(self._field_label("Recurrence"), self._recurrence_input)

        reminder_row = QWidget()
        reminder_layout = QHBoxLayout(reminder_row)
        reminder_layout.setContentsMargins(0, 0, 0, 0)
        reminder_layout.setSpacing(6)

        self._reminder_mode_input = QComboBox()
        for key, label in REMINDER_OPTIONS:
            self._reminder_mode_input.addItem(label, key)
        self._reminder_mode_input.currentIndexChanged.connect(self._on_reminder_mode_changed)
        reminder_layout.addWidget(self._reminder_mode_input, 1)

        self._reminder_minutes_input = QSpinBox()
        self._reminder_minutes_input.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._reminder_minutes_input.setRange(0, 40320)  # up to 4 weeks
        self._reminder_minutes_input.setSingleStep(5)
        self._reminder_minutes_input.setSuffix(" min")
        self._reminder_minutes_input.setValue(10)
        reminder_layout.addLayout(self._wrap_spin(self._reminder_minutes_input), 0)

        form.addRow(self._field_label("Reminder"), reminder_row)

        self._description_input = QTextEdit()
        self._description_input.setPlaceholderText("Description")
        self._description_input.setFixedHeight(80)
        form.addRow(self._field_label("Description"), self._description_input)

        outer.addLayout(form)

        self._error_lbl = QLabel("")
        self._error_lbl.setObjectName("formError")
        self._error_lbl.setWordWrap(True)
        outer.addWidget(self._error_lbl)

        outer.addStretch()

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(6)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("cancelBtn")
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self._cancel_btn)

        self._save_btn = QPushButton("Save")
        self._save_btn.setObjectName("saveBtn")
        self._save_btn.clicked.connect(self._on_submit)
        btn_layout.addWidget(self._save_btn)

        outer.addWidget(btn_row)
        self._apply_color_combo_style()

    def _wrap_spin(self, spin_widget) -> QHBoxLayout:
        """Wrap a QTimeEdit/QSpinBox with explicit ▲/▼ buttons."""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(spin_widget, 1)

        btn_col = QVBoxLayout()
        btn_col.setContentsMargins(0, 0, 0, 0)
        btn_col.setSpacing(0)

        up_btn = QToolButton()
        up_btn.setText("▲")
        up_btn.setFixedSize(20, 14)
        up_btn.setAutoRepeat(True)
        up_btn.setAutoRepeatInterval(120)
        up_btn.clicked.connect(spin_widget.stepUp)
        btn_col.addWidget(up_btn)

        down_btn = QToolButton()
        down_btn.setText("▼")
        down_btn.setFixedSize(20, 14)
        down_btn.setAutoRepeat(True)
        down_btn.setAutoRepeatInterval(120)
        down_btn.clicked.connect(spin_widget.stepDown)
        btn_col.addWidget(down_btn)

        layout.addLayout(btn_col)

        style = self._spin_btn_style()
        up_btn.setStyleSheet(style)
        down_btn.setStyleSheet(style)
        self._spin_btns = getattr(self, "_spin_btns", [])
        self._spin_btns.extend([up_btn, down_btn])
        return layout

    def _spin_btn_style(self) -> str:
        return f"""
            QToolButton {{
                background: {c("titlebar")};
                color: {c("text")};
                border: 1px solid {c("action_btn_border")};
                font-size: 7px;
                padding: 0;
            }}
            QToolButton:hover {{
                background: {c("calendar_tool_hover_bg")};
                border-color: {c("action_btn_border_hover")};
            }}
        """

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("formField")
        return lbl

    def _set_color_id(self, color_id: str) -> None:
        idx = self._color_input.findData(color_id)
        if idx < 0:
            idx = self._color_input.findData("9")
        self._color_input.setCurrentIndex(max(0, idx))
        self._apply_color_combo_style()

    def _set_recurrence(self, mode: str) -> None:
        idx = self._recurrence_input.findData(mode)
        if idx < 0:
            idx = self._recurrence_input.findData("none")
        self._recurrence_input.setCurrentIndex(max(0, idx))

    def _set_reminder(self, mode: str, minutes: int) -> None:
        idx = self._reminder_mode_input.findData(mode)
        if idx < 0:
            idx = self._reminder_mode_input.findData("default")
        self._reminder_mode_input.setCurrentIndex(max(0, idx))
        self._reminder_minutes_input.setValue(max(0, int(minutes)))
        self._on_reminder_mode_changed()

    def _set_reminder_from_event(self, event: dict) -> None:
        reminders = event.get("reminders") or {}
        if reminders.get("useDefault", False):
            self._set_reminder("default", 10)
            return
        overrides = reminders.get("overrides") or []
        if not overrides:
            self._set_reminder("none", 10)
            return
        first = overrides[0]
        mode = str(first.get("method") or "popup")
        minutes = int(first.get("minutes") or 10)
        if mode not in {"popup", "email"}:
            mode = "popup"
        self._set_reminder(mode, minutes)

    def _read_recurrence_mode(self, event: dict) -> str:
        recurrence = event.get("recurrence") or []
        for rule in recurrence:
            if "FREQ=DAILY" in rule:
                return "daily"
            if "FREQ=MONTHLY" in rule:
                return "monthly"
            if "FREQ=YEARLY" in rule:
                return "yearly"
        return "none"

    def _on_submit(self):
        title = self._title_input.text().strip()
        if not title:
            self._error_lbl.setText("Title is required.")
            return

        date = self._date_input.date().toPyDate()
        start_qt = self._start_input.time()
        end_qt = self._end_input.time()
        start_dt = datetime.datetime.combine(date, datetime.time(start_qt.hour(), start_qt.minute()))
        end_dt = datetime.datetime.combine(date, datetime.time(end_qt.hour(), end_qt.minute()))
        if end_dt <= start_dt:
            end_dt = start_dt + datetime.timedelta(hours=1)
            self._end_input.setTime(QTime(end_dt.hour, end_dt.minute))

        if self._editing_event_id is None and date < datetime.date.today():
            QMessageBox.warning(
                self,
                "Invalid date",
                "You cannot create a new event in a past date.",
            )
            return

        tz = datetime.datetime.now().astimezone().tzinfo
        payload = {
            "summary": title,
            "description": self._description_input.toPlainText().strip(),
            "colorId": str(self._color_input.currentData()),
            "start": {"dateTime": start_dt.replace(tzinfo=tz).isoformat()},
            "end": {"dateTime": end_dt.replace(tzinfo=tz).isoformat()},
        }
        recurrence_mode = str(self._recurrence_input.currentData())
        recurrence_map = {
            "daily": "RRULE:FREQ=DAILY",
            "monthly": "RRULE:FREQ=MONTHLY",
            "yearly": "RRULE:FREQ=YEARLY",
        }
        if recurrence_mode in recurrence_map:
            payload["recurrence"] = [recurrence_map[recurrence_mode]]
        elif self._editing_event_id is not None:
            payload["recurrence"] = []

        reminder_mode = str(self._reminder_mode_input.currentData())
        reminder_minutes = int(self._reminder_minutes_input.value())
        if reminder_mode == "default":
            payload["reminders"] = {"useDefault": True}
        elif reminder_mode == "none":
            payload["reminders"] = {"useDefault": False, "overrides": []}
        else:
            payload["reminders"] = {
                "useDefault": False,
                "overrides": [{"method": reminder_mode, "minutes": reminder_minutes}],
            }
        self._error_lbl.setText("")
        self.submit_requested.emit(self._editing_event_id, payload)

    def _on_cancel(self):
        self.close_panel()
        self.cancel_requested.emit()

    def _animate_to(self, width: int, hide_after: bool):
        self._hide_after_anim = hide_after
        self.setVisible(True)
        self._animation.stop()
        self._animation.setStartValue(self.maximumWidth())
        self._animation.setEndValue(width)
        self.width_changed.emit(self.maximumWidth())
        self._animation.start()

    def _on_animation_finished(self):
        self.width_changed.emit(self.maximumWidth())
        if self._hide_after_anim and self.maximumWidth() == 0:
            self.setVisible(False)

    def _on_animation_value_changed(self, value):
        self.width_changed.emit(int(value))

    def _on_reminder_mode_changed(self):
        mode = str(self._reminder_mode_input.currentData())
        self._reminder_minutes_input.setEnabled(mode in {"popup", "email"})

    def _apply_color_combo_style(self):
        self._color_input.setStyleSheet(
            f"""
            QComboBox {{
                background: {c("bg")};
                color: {c("text")};
                border: 1px solid {c("action_btn_border")};
                border-radius: 4px;
                padding: 5px;
                font-size: 11px;
            }}
            QComboBox:focus {{
                border: 1px solid {c("accent")};
            }}
            QComboBox QAbstractItemView {{
                background: {c("bg")};
                color: {c("text")};
                border: 1px solid {c("border")};
                selection-background-color: {c("accent")};
                selection-color: {c("bg")};
            }}
            """
        )

    def _color_item_icon(self, color_id: str) -> QIcon:
        bg = GOOGLE_COLORS.get(color_id, GOOGLE_COLORS["9"])
        pix = QPixmap(14, 10)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor(c("action_btn_border_hover")))
        painter.setBrush(QColor(bg))
        painter.drawRoundedRect(0, 0, 13, 9, 2, 2)
        painter.end()
        return QIcon(pix)
