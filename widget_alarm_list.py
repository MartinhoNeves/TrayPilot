"""
widget_alarm_list.py — alarm list panel for the Alarms tab.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from alarms import Alarm, recurrence_label
from colour_theme import c


class _AlarmRow(QWidget):
    clicked = pyqtSignal(object)
    toggled = pyqtSignal(str, bool)

    def __init__(self, alarm: Alarm):
        super().__init__()
        self.alarm = alarm
        self._selected = False
        self._hovered = False
        self._build()
        self._apply_style()

    def _build(self):
        self.setObjectName("alarmRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 7, 10, 7)
        lay.setSpacing(8)

        dot = QLabel("●")
        dot.setStyleSheet(f"color: {c('accent') if self.alarm.enabled else c('dim')};")
        lay.addWidget(dot)

        title = QLabel(self.alarm.title)
        title.setStyleSheet(f"color: {c('text')}; font-size: 12px;")
        lay.addWidget(title, 1)

        next_lbl = QLabel(self.alarm.next_fire.strftime("%d %b %H:%M"))
        next_lbl.setStyleSheet(f"color: {c('dim')}; font-size: 11px;")
        lay.addWidget(next_lbl)

        rec_lbl = QLabel(recurrence_label(self.alarm.recurrence))
        rec_lbl.setStyleSheet(f"color: {c('dim')}; font-size: 11px; min-width: 58px;")
        lay.addWidget(rec_lbl)

        self._enabled = QCheckBox("On")
        self._enabled.setChecked(self.alarm.enabled)
        self._enabled.clicked.connect(lambda checked: self.toggled.emit(self.alarm.id, bool(checked)))
        lay.addWidget(self._enabled)

    def set_selected(self, selected: bool):
        self._selected = selected
        self._apply_style()

    def mousePressEvent(self, event):
        self.clicked.emit(self.alarm)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self._hovered = True
        self._apply_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._apply_style()
        super().leaveEvent(event)

    def _apply_style(self):
        if self._selected:
            self.setStyleSheet(
                f"QWidget#alarmRow {{ background: {c('row_selected_bg')}; border-left: 3px solid {c('accent')}; }}"
            )
        elif self._hovered:
            self.setStyleSheet(
                f"QWidget#alarmRow {{ background: {c('row_hover_bg')}; border-left: 3px solid transparent; }}"
            )
        else:
            self.setStyleSheet("QWidget#alarmRow { background: transparent; border-left: 3px solid transparent; }")


class AlarmListWidget(QWidget):
    add_requested = pyqtSignal()
    edit_requested = pyqtSignal(object)
    delete_requested = pyqtSignal(object)
    enabled_toggled = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[_AlarmRow] = []
        self._selected: Alarm | None = None
        self._build_ui()
        self._apply_style()

    def set_alarms(self, alarms: list[Alarm]) -> None:
        self._rows.clear()
        self._selected = None
        self._edit_btn.setVisible(False)
        self._delete_btn.setVisible(False)
        while self._scroll_layout.count():
            item = self._scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for alarm in alarms:
            row = _AlarmRow(alarm)
            row.clicked.connect(self._on_row_clicked)
            row.toggled.connect(self.enabled_toggled)
            self._rows.append(row)
            self._scroll_layout.addWidget(row)
        if not alarms:
            empty = QLabel("No alarms yet")
            empty.setStyleSheet(f"color: {c('muted')}; font-size: 12px; font-style: italic; padding: 14px;")
            self._scroll_layout.addWidget(empty)
        self._scroll_layout.addStretch()

    def apply_theme(self):
        self._apply_style()
        for row in self._rows:
            row._apply_style()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QWidget()
        toolbar.setObjectName("alarmToolbar")
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(14, 12, 14, 10)
        tl.setSpacing(6)
        lbl = QLabel("ALARMS")
        lbl.setObjectName("alarmTitle")
        tl.addWidget(lbl)
        tl.addStretch()
        self._edit_btn = QPushButton("Edit")
        self._delete_btn = QPushButton("Delete")
        self._add_btn = QPushButton("+ Add Alarm")
        self._edit_btn.setVisible(False)
        self._delete_btn.setVisible(False)
        self._edit_btn.clicked.connect(lambda: self._selected and self.edit_requested.emit(self._selected))
        self._delete_btn.clicked.connect(lambda: self._selected and self.delete_requested.emit(self._selected))
        self._add_btn.clicked.connect(self.add_requested)
        tl.addWidget(self._edit_btn)
        tl.addWidget(self._delete_btn)
        tl.addWidget(self._add_btn)
        root.addWidget(toolbar)

        sep = QWidget()
        sep.setObjectName("alarmSep")
        sep.setFixedHeight(1)
        root.addWidget(sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_content = QWidget()
        self._scroll_layout = QVBoxLayout(self._scroll_content)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(0)
        scroll.setWidget(self._scroll_content)
        self._scroll = scroll
        root.addWidget(scroll, 1)

    def _on_row_clicked(self, alarm: Alarm):
        self._selected = alarm
        self._edit_btn.setVisible(True)
        self._delete_btn.setVisible(True)
        for row in self._rows:
            row.set_selected(row.alarm.id == alarm.id)

    def _apply_style(self):
        btn = f"""
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
        self.setStyleSheet(
            f"""
            QWidget#alarmToolbar {{ background: {c("bg")}; }}
            QLabel#alarmTitle {{ color: {c("accent")}; font-size: 12px; font-weight: 600; }}
            QWidget#alarmSep {{ background: {c("border")}; }}
            """
        )
        self._edit_btn.setStyleSheet(btn)
        self._delete_btn.setStyleSheet(btn.replace(c("dim"), c("danger")))
        self._add_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: {c("agenda_btn_bg")};
                border: 1px solid {c("agenda_btn_border")};
                border-radius: 5px;
                color: {c("accent")};
                font-size: 11px;
                padding: 5px 10px;
            }}
            QPushButton:hover {{
                background: {c("agenda_btn_bg_hover")};
                border-color: {c("agenda_btn_border_hover")};
            }}
            """
        )
