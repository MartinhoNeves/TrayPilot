"""
alarm_notification.py — alarm popup dialog with dismiss/snooze controls.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from alarms import Alarm
from colour_theme import c
from settings import get_default_snooze_minutes


class AlarmNotificationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._alarm_id: str | None = None
        self.setWindowTitle("Alarm")
        self.setModal(False)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setMinimumWidth(340)
        self._build_ui()
        self._apply_theme()

    def present(self, alarm: Alarm) -> None:
        self._alarm_id = alarm.id
        self._title_lbl.setText(alarm.title or "Alarm")
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

    def current_alarm_id(self) -> str | None:
        return self._alarm_id

    def selected_snooze_minutes(self) -> int:
        value = str(self._snooze_combo.currentData())
        if value == "custom":
            return int(self._custom_minutes.value())
        return int(value)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        self._title_lbl = QLabel("Alarm")
        self._title_lbl.setObjectName("alarmTitle")
        root.addWidget(self._title_lbl)

        self._detail_lbl = QLabel("")
        self._detail_lbl.setObjectName("alarmDetail")
        root.addWidget(self._detail_lbl)

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
        self.dismiss_btn = QPushButton("Dismiss")
        self.snooze_btn = QPushButton("Snooze")
        buttons.addWidget(self.dismiss_btn)
        buttons.addWidget(self.snooze_btn)
        root.addLayout(buttons)

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
            QLabel#alarmTitle {{
                color: {c("accent")};
                font-size: 14px;
                font-weight: 600;
            }}
            QLabel#alarmDetail {{
                color: {c("dim")};
                font-size: 11px;
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
            QPushButton#dismissBtn {{
                background: transparent;
                color: {c("dim")};
                border: 1px solid {c("action_btn_border")};
            }}
            QPushButton#snoozeBtn {{
                background: {c("agenda_btn_bg")};
                color: {c("accent")};
                border: 1px solid {c("agenda_btn_border")};
            }}
            """
        )
        self.dismiss_btn.setObjectName("dismissBtn")
        self.snooze_btn.setObjectName("snoozeBtn")
