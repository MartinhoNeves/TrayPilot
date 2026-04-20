"""
note_notification.py — read-only note reminder dialog (Dismiss / Snooze / Edit note).
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from alarms import Alarm
from colour_theme import c
from settings import get_default_snooze_minutes


class NoteReminderDialog(QDialog):
    edit_note_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._alarm_id: str | None = None
        self._note_id: str | None = None
        self.setWindowTitle("Note reminder")
        self.setModal(False)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setMinimumWidth(380)
        self.setMinimumHeight(220)
        self._build_ui()
        self._apply_theme()

    def present(self, alarm: Alarm, *, title: str, body: str, note_id: str) -> None:
        self._alarm_id = alarm.id
        self._note_id = note_id
        self._title_lbl.setText(title.strip() or "Note")
        self._body.setPlainText(body)
        self._detail_lbl.setText(f"Scheduled: {alarm.next_fire.strftime('%Y-%m-%d %H:%M')}")
        dm = get_default_snooze_minutes()
        idx_map = {5: 0, 10: 1, 15: 2, 30: 3}
        self._snooze_combo.blockSignals(True)
        self._snooze_combo.setCurrentIndex(idx_map.get(dm, 1))
        self._snooze_combo.blockSignals(False)
        self._on_snooze_changed()
        self.show()
        self.raise_()
        self.activateWindow()

        def _after_show():
            self._snooze_combo.hidePopup()
            self.snooze_btn.setFocus(Qt.FocusReason.OtherFocusReason)

        QTimer.singleShot(0, _after_show)

    def current_alarm_id(self) -> str | None:
        return self._alarm_id

    def current_note_id(self) -> str | None:
        return self._note_id

    def selected_snooze_minutes(self) -> int:
        value = str(self._snooze_combo.currentData())
        if value == "custom":
            return int(self._custom_minutes.value())
        return int(value)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        self._title_lbl = QLabel("Note")
        self._title_lbl.setObjectName("noteReminderTitle")
        root.addWidget(self._title_lbl)

        self._detail_lbl = QLabel("")
        self._detail_lbl.setObjectName("noteReminderDetail")
        root.addWidget(self._detail_lbl)

        self._body = QPlainTextEdit()
        self._body.setReadOnly(True)
        self._body.setObjectName("noteReminderBody")
        self._body.setMinimumHeight(120)
        root.addWidget(self._body, 1)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        self._snooze_combo = QComboBox()
        self._snooze_combo.addItem("5 min", "5")
        self._snooze_combo.addItem("10 min", "10")
        self._snooze_combo.addItem("15 min", "15")
        self._snooze_combo.addItem("30 min", "30")
        self._snooze_combo.addItem("Custom", "custom")
        self._snooze_combo.currentIndexChanged.connect(self._on_snooze_changed)
        row_layout.addWidget(self._snooze_combo, 1)

        self._custom_minutes = QSpinBox()
        self._custom_minutes.setRange(1, 1440)
        self._custom_minutes.setValue(15)
        self._custom_minutes.setSuffix(" min")
        self._custom_minutes.setVisible(False)
        row_layout.addWidget(self._custom_minutes)

        root.addWidget(row)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.edit_btn = QPushButton("Edit note")
        self.dismiss_btn = QPushButton("Dismiss")
        self.snooze_btn = QPushButton("Snooze")
        buttons.addWidget(self.edit_btn)
        buttons.addWidget(self.dismiss_btn)
        buttons.addWidget(self.snooze_btn)
        root.addLayout(buttons)

        self.edit_btn.clicked.connect(self._on_edit_clicked)

    def _on_edit_clicked(self):
        nid = self._note_id or ""
        self.hide()
        if nid:
            self.edit_note_requested.emit(nid)

    def _on_snooze_changed(self):
        self._custom_minutes.setVisible(str(self._snooze_combo.currentData()) == "custom")

    def _apply_theme(self):
        self.setStyleSheet(
            f"""
            QDialog {{
                background: {c("titlebar")};
                color: {c("text")};
                border: 1px solid {c("border")};
                border-radius: 8px;
            }}
            QLabel#noteReminderTitle {{
                color: {c("accent")};
                font-size: 14px;
                font-weight: 600;
            }}
            QLabel#noteReminderDetail {{
                color: {c("dim")};
                font-size: 11px;
            }}
            QPlainTextEdit#noteReminderBody {{
                background: {c("bg")};
                color: {c("text")};
                border: 1px solid {c("action_btn_border")};
                border-radius: 4px;
                padding: 8px;
                font-size: 12px;
            }}
            QComboBox, QSpinBox {{
                background: {c("bg")};
                color: {c("text")};
                border: 1px solid {c("action_btn_border")};
                border-radius: 4px;
                padding: 5px;
                font-size: 11px;
            }}
            QPushButton {{
                border-radius: 5px;
                padding: 6px 10px;
                font-size: 11px;
            }}
            QPushButton#noteDismissBtn {{
                background: transparent;
                color: {c("dim")};
                border: 1px solid {c("action_btn_border")};
            }}
            QPushButton#noteSnoozeBtn {{
                background: {c("agenda_btn_bg")};
                color: {c("accent")};
                border: 1px solid {c("agenda_btn_border")};
            }}
            QPushButton#noteEditBtn {{
                background: {c("titlebar")};
                color: {c("text")};
                border: 1px solid {c("action_btn_border")};
            }}
            """
        )
        self.dismiss_btn.setObjectName("noteDismissBtn")
        self.snooze_btn.setObjectName("noteSnoozeBtn")
        self.edit_btn.setObjectName("noteEditBtn")
