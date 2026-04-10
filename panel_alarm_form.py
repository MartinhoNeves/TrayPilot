"""
panel_alarm_form.py — slide-in alarm create/edit form.
"""
from __future__ import annotations

import datetime as dt

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QTime, Qt, pyqtSignal
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
    QTimeEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from alarms import (
    Alarm,
    RECURRENCE_DAILY,
    RECURRENCE_MONTHLY,
    RECURRENCE_NONE,
    RECURRENCE_WEEKLY,
    RECURRENCE_YEARLY,
    SOUND_ALARM,
    SOUND_CALENDAR,
    SOUND_EMAIL,
    SOUND_NONE,
)
from colour_theme import c

FORM_WIDTH = 300
ANIMATION_MS = 250


class AlarmFormPanel(QWidget):
    submit_requested = pyqtSignal(object, dict)  # alarm_id | None, payload
    cancel_requested = pyqtSignal()
    width_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._editing_alarm_id: str | None = None
        self._open_width = FORM_WIDTH
        self._events: list[dict] = []
        self._anim = QPropertyAnimation(self, b"maximumWidth", self)
        self._anim.setDuration(ANIMATION_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hide_after = False
        self._spin_btns: list[QToolButton] = []
        self.setMinimumWidth(0)
        self.setMaximumWidth(0)
        self.setVisible(False)
        self._build_ui()
        self.apply_theme()
        self._anim.finished.connect(self._on_anim_finished)
        self._anim.valueChanged.connect(lambda v: self.width_changed.emit(int(v)))

    def set_open_width(self, width: int):
        self._open_width = max(FORM_WIDTH, int(width))
        if self.isVisible() and self.maximumWidth() > 0:
            self.setMaximumWidth(self._open_width)

    def set_calendar_events(self, events: list[dict]):
        self._events = list(events)
        self._event_combo.clear()
        self._event_combo.addItem("None", "")
        for evt in self._events:
            event_id = str(evt.get("id") or "")
            title = str(evt.get("summary") or "(No title)")
            if event_id:
                self._event_combo.addItem(f"{self._event_date_column(evt)}  |  {title}", event_id)

    def open_for_new(self, default_dt: dt.datetime | None = None, width: int | None = None):
        if width is not None:
            self._open_width = max(FORM_WIDTH, int(width))
        self._editing_alarm_id = None
        self._title.setText("")
        when = default_dt or (dt.datetime.now().astimezone() + dt.timedelta(minutes=10))
        self._date.setDate(when.date())
        self._time.setTime(QTime(when.hour, when.minute))
        self._set_combo_data(self._recurrence, RECURRENCE_NONE)
        self._set_combo_data(self._sound, SOUND_ALARM)
        self._set_combo_data(self._event_combo, "")
        self._offset.setValue(10)
        self._error.setText("")
        self._heading.setText("New alarm")
        self._save.setText("Save")
        self._animate_to(self._open_width, hide_after=False)

    def open_for_edit(self, alarm: Alarm, width: int | None = None):
        if width is not None:
            self._open_width = max(FORM_WIDTH, int(width))
        self._editing_alarm_id = alarm.id
        self._title.setText(alarm.title)
        self._date.setDate(alarm.next_fire.date())
        self._time.setTime(QTime(alarm.next_fire.hour, alarm.next_fire.minute))
        self._set_combo_data(self._recurrence, alarm.recurrence)
        self._set_combo_data(self._sound, alarm.sound)
        self._set_combo_data(self._event_combo, alarm.linked_event_id)
        self._offset.setValue(int(alarm.linked_offset_minutes))
        self._error.setText("")
        self._heading.setText("Edit alarm")
        self._save.setText("Save")
        self._animate_to(self._open_width, hide_after=False)

    def close_panel(self):
        self._error.setText("")
        self._animate_to(0, hide_after=True)

    def apply_theme(self):
        self.setStyleSheet(
            f"""
            QWidget#alarmForm {{
                background: {c("titlebar")};
                border-left: 1px solid {c("border")};
            }}
            QLabel#alarmFormHeading {{
                color: {c("accent")};
                font-size: 12px;
                font-weight: 600;
            }}
            QLabel#alarmFormField {{ color: {c("text")}; font-size: 12px; }}
            QLabel#alarmFormError {{ color: {c("danger")}; font-size: 11px; }}
            QLineEdit, QDateEdit, QTimeEdit, QComboBox, QSpinBox {{
                background: {c("bg")};
                color: {c("text")};
                border: 1px solid {c("action_btn_border")};
                border-radius: 4px;
                padding: 5px;
                font-size: 11px;
            }}
            QLineEdit:hover, QDateEdit:hover, QTimeEdit:hover, QComboBox:hover, QSpinBox:hover {{
                border: 1px solid {c("action_btn_border_hover")};
                background: {c("titlebar")};
            }}
            QComboBox#alarmEventLinkCombo, QComboBox#alarmEventLinkCombo QAbstractItemView {{
                font-family: Consolas, 'Courier New', monospace;
            }}
            QTimeEdit, QSpinBox {{
                border-top-right-radius: 0;
                border-bottom-right-radius: 0;
            }}
            QPushButton#alarmSave {{
                background: {c("agenda_btn_bg")};
                color: {c("accent")};
                border: 1px solid {c("agenda_btn_border")};
                border-radius: 5px;
                padding: 5px 10px;
            }}
            QPushButton#alarmSave:hover {{
                background: {c("agenda_btn_bg_hover")};
                border-color: {c("agenda_btn_border_hover")};
            }}
            QPushButton#alarmCancel {{
                background: transparent;
                color: {c("dim")};
                border: 1px solid {c("action_btn_border")};
                border-radius: 5px;
                padding: 5px 10px;
            }}
            QPushButton#alarmCancel:hover {{
                color: {c("text")};
                border-color: {c("action_btn_border_hover")};
                background: {c("titlebar")};
            }}
            """
        )
        for btn in self._spin_btns:
            btn.setStyleSheet(self._spin_btn_style())

    def _build_ui(self):
        self.setObjectName("alarmForm")
        out = QVBoxLayout(self)
        out.setContentsMargins(10, 10, 10, 10)
        out.setSpacing(8)
        self._heading = QLabel("New alarm")
        self._heading.setObjectName("alarmFormHeading")
        out.addWidget(self._heading)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)
        self._title = QLineEdit()
        self._title.setPlaceholderText("Alarm title")
        form.addRow(self._label("Title"), self._title)
        self._date = QDateEdit()
        self._date.setCalendarPopup(True)
        self._date.setDate(dt.datetime.now().astimezone().date())
        self._date.setDisplayFormat("ddd dd MMM yyyy")
        form.addRow(self._label("Date"), self._date)
        self._time = QTimeEdit()
        self._time.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._time.setDisplayFormat("HH:mm")
        now = dt.datetime.now().astimezone() + dt.timedelta(minutes=10)
        self._time.setTime(QTime(now.hour, now.minute))
        form.addRow(self._label("Time"), self._wrap_spin(self._time))
        self._recurrence = QComboBox()
        self._recurrence.addItem("Once", RECURRENCE_NONE)
        self._recurrence.addItem("Daily", RECURRENCE_DAILY)
        self._recurrence.addItem("Weekly", RECURRENCE_WEEKLY)
        self._recurrence.addItem("Monthly", RECURRENCE_MONTHLY)
        self._recurrence.addItem("Yearly", RECURRENCE_YEARLY)
        form.addRow(self._label("Recurrence"), self._recurrence)
        self._sound = QComboBox()
        self._sound.addItem("Default alarm", SOUND_ALARM)
        self._sound.addItem("Calendar", SOUND_CALENDAR)
        self._sound.addItem("Email", SOUND_EMAIL)
        self._sound.addItem("Silent", SOUND_NONE)
        form.addRow(self._label("Sound"), self._sound)
        self._event_combo = QComboBox()
        self._event_combo.setObjectName("alarmEventLinkCombo")
        self._event_combo.addItem("None", "")
        form.addRow(self._label("Calendar link"), self._event_combo)
        self._offset = QSpinBox()
        self._offset.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._offset.setRange(-10_080, 10_080)
        self._offset.setSingleStep(5)
        self._offset.setSuffix(" min")
        self._offset.setValue(10)
        form.addRow(self._label("Offset"), self._wrap_spin(self._offset))
        out.addLayout(form)
        self._error = QLabel("")
        self._error.setObjectName("alarmFormError")
        self._error.setWordWrap(True)
        out.addWidget(self._error)
        out.addStretch()
        row = QHBoxLayout()
        self._cancel = QPushButton("Cancel")
        self._cancel.setObjectName("alarmCancel")
        self._cancel.clicked.connect(self._on_cancel)
        row.addWidget(self._cancel)
        self._save = QPushButton("Save")
        self._save.setObjectName("alarmSave")
        self._save.clicked.connect(self._on_submit)
        row.addWidget(self._save)
        out.addLayout(row)

    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("alarmFormField")
        lbl.setMinimumWidth(84)
        return lbl

    def _wrap_spin(self, spin_widget) -> QWidget:
        box = QWidget()
        layout = QHBoxLayout(box)
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
        up_btn.setStyleSheet(self._spin_btn_style())
        btn_col.addWidget(up_btn)

        down_btn = QToolButton()
        down_btn.setText("▼")
        down_btn.setFixedSize(20, 14)
        down_btn.setAutoRepeat(True)
        down_btn.setAutoRepeatInterval(120)
        down_btn.clicked.connect(spin_widget.stepDown)
        down_btn.setStyleSheet(self._spin_btn_style())
        btn_col.addWidget(down_btn)

        self._spin_btns.extend([up_btn, down_btn])
        layout.addLayout(btn_col)
        return box

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

    def _on_submit(self):
        title = self._title.text().strip()
        if not title:
            self._error.setText("Title is required.")
            return
        selected_date = self._date.date().toPyDate()
        selected_time = self._time.time().toPyTime()
        when = dt.datetime.combine(selected_date, selected_time, tzinfo=dt.datetime.now().astimezone().tzinfo)
        if self._editing_alarm_id is None and when <= dt.datetime.now().astimezone():
            QMessageBox.warning(self, "Invalid date", "Alarm must be scheduled in the future.")
            return
        payload = {
            "title": title,
            "next_fire_iso": when.isoformat(),
            "recurrence": str(self._recurrence.currentData()),
            "sound": str(self._sound.currentData()),
            "linked_event_id": str(self._event_combo.currentData() or ""),
            "linked_offset_minutes": int(self._offset.value()),
        }
        self._error.setText("")
        self.submit_requested.emit(self._editing_alarm_id, payload)

    def _on_cancel(self):
        self.close_panel()
        self.cancel_requested.emit()

    def _animate_to(self, width: int, hide_after: bool):
        self._hide_after = hide_after
        self.setVisible(True)
        self._anim.stop()
        self._anim.setStartValue(self.maximumWidth())
        self._anim.setEndValue(width)
        self.width_changed.emit(self.maximumWidth())
        self._anim.start()

    def _on_anim_finished(self):
        self.width_changed.emit(self.maximumWidth())
        if self._hide_after and self.maximumWidth() == 0:
            self.setVisible(False)

    def _set_combo_data(self, combo: QComboBox, value: str):
        idx = combo.findData(value)
        combo.setCurrentIndex(max(0, idx))

    def _event_date_column(self, event: dict) -> str:
        start = event.get("start") or {}
        if "dateTime" in start:
            try:
                when = dt.datetime.fromisoformat(str(start["dateTime"]))
                return when.strftime("%d %b %Y %H:%M")
            except Exception:
                return "?? ??? ???? ??:??"
        if "date" in start:
            try:
                day = dt.date.fromisoformat(str(start["date"]))
                return f"{day.strftime('%d %b %Y')} --:--"
            except Exception:
                return "?? ??? ???? ??:??"
        return "?? ??? ???? ??:??"
