"""
widget_settings.py — Settings tab: appearance (incl. launch at startup), Gmail, alarms, notifications.
Mail poll interval uses the same ▲/▼ QToolButton pattern as `panel_event_form.EventFormPanel`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from colour_theme import c, theme_mode, toggle_theme_mode
from paths import Paths
from settings import (
    get_alarm_sound_default,
    get_always_on_top,
    get_default_snooze_minutes,
    get_mail_awareness_enabled,
    get_mail_poll_interval_minutes,
    get_notify_balloon_alarm,
    get_notify_balloon_new_mail,
    set_alarm_sound_default,
    set_always_on_top,
    set_default_snooze_minutes,
    set_mail_awareness_enabled,
    set_mail_poll_interval_minutes,
    set_notify_balloon_alarm,
    set_notify_balloon_new_mail,
    set_theme_mode as persist_theme_mode,
)
from windows_startup import is_run_at_startup_enabled, set_run_at_startup

if TYPE_CHECKING:
    from gmail_client import GmailClient


def _spin_btn_style() -> str:
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


def _wrap_mail_interval_spin(spin: QSpinBox) -> tuple[QWidget, list[QToolButton]]:
    """Match `EventFormPanel._wrap_spin`: NoButtons spin + 20×14 ▲/▼ with auto-repeat."""
    box = QWidget()
    lay = QHBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    lay.addWidget(spin, 1)

    btn_col = QVBoxLayout()
    btn_col.setContentsMargins(0, 0, 0, 0)
    btn_col.setSpacing(0)

    up_btn = QToolButton()
    up_btn.setText("▲")
    up_btn.setFixedSize(20, 14)
    up_btn.setAutoRepeat(True)
    up_btn.setAutoRepeatInterval(120)
    up_btn.clicked.connect(spin.stepUp)
    btn_col.addWidget(up_btn)

    down_btn = QToolButton()
    down_btn.setText("▼")
    down_btn.setFixedSize(20, 14)
    down_btn.setAutoRepeat(True)
    down_btn.setAutoRepeatInterval(120)
    down_btn.clicked.connect(spin.stepDown)
    btn_col.addWidget(down_btn)

    lay.addLayout(btn_col)
    return box, [up_btn, down_btn]


class SettingsWidget(QWidget):
    """Scrollable settings; `appearance_changed` after theme or always-on-top change."""

    appearance_changed = pyqtSignal()
    mail_settings_changed = pyqtSignal()

    def __init__(self, gmail_client: "GmailClient | None" = None, parent=None):
        super().__init__(parent)
        self._gmail = gmail_client
        self._always_on_top = get_always_on_top()
        self._mail_interval_spin_btns: list[QToolButton] = []
        self._build_ui()
        self._load_from_settings()
        self.apply_theme()

    def _section_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("settingsSectionTitle")
        return lbl

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("settingsFieldLbl")
        return lbl

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        panel = QWidget()
        panel.setObjectName("settingsPanel")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        root = QVBoxLayout(panel)
        root.setContentsMargins(16, 14, 16, 20)
        root.setSpacing(0)

        # ── Appearance (single row: theme, always-on-top, startup) ───────────
        root.addWidget(self._section_title("Appearance"))

        app_row = QHBoxLayout()
        app_row.setContentsMargins(0, 0, 0, 8)
        app_row.setSpacing(10)

        app_row.addWidget(self._field_label("Theme"))
        self._theme_btn = QToolButton()
        self._theme_btn.setObjectName("themeToggle")
        self._theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._theme_btn.clicked.connect(self._on_theme_clicked)
        app_row.addWidget(self._theme_btn)

        app_row.addWidget(self._field_label("Always on top"))
        self._always_btn = QToolButton()
        self._always_btn.setObjectName("alwaysOnTopToggle")
        self._always_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._always_btn.clicked.connect(self._on_always_clicked)
        app_row.addWidget(self._always_btn)

        self._startup_chk = QCheckBox("Launch at Windows startup")
        self._startup_chk.setObjectName("settingsStartupChk")
        self._startup_chk.stateChanged.connect(self._on_startup_changed)
        app_row.addWidget(self._startup_chk)

        app_row.addStretch(1)
        root.addLayout(app_row)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setObjectName("settingsSep")
        root.addWidget(sep1)

        # ── Gmail ─────────────────────────────────────────────────────────────
        root.addWidget(self._section_title("Gmail"))

        mail_form = QFormLayout()
        mail_form.setContentsMargins(0, 0, 0, 8)
        mail_form.setSpacing(8)
        mail_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._mail_enable_chk = QCheckBox()
        self._mail_enable_chk.setObjectName("settingsMailEnableChk")
        self._mail_enable_chk.stateChanged.connect(self._on_mail_enable_changed)
        mail_form.addRow(self._field_label("Enable Gmail awareness"), self._mail_enable_chk)

        self._mail_interval_spin = QSpinBox()
        self._mail_interval_spin.setObjectName("settingsMailIntervalSpin")
        self._mail_interval_spin.setRange(1, 60)
        self._mail_interval_spin.setSuffix(" min")
        self._mail_interval_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._mail_interval_spin.setMinimumWidth(72)
        self._mail_interval_spin.valueChanged.connect(self._on_mail_interval_changed)
        interval_wrap, btns = _wrap_mail_interval_spin(self._mail_interval_spin)
        self._mail_interval_spin_btns = btns
        mail_form.addRow(self._field_label("Check every"), interval_wrap)

        root.addLayout(mail_form)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setObjectName("settingsSep")
        root.addWidget(sep2)

        # ── Alarms (sound + snooze on one row) ────────────────────────────────
        root.addWidget(self._section_title("Alarms"))

        alarm_row = QHBoxLayout()
        alarm_row.setContentsMargins(0, 0, 0, 8)
        alarm_row.setSpacing(10)

        alarm_row.addWidget(self._field_label("Default alarm sound"))
        self._alarm_sound_combo = QComboBox()
        self._alarm_sound_combo.setObjectName("settingsAlarmSoundCombo")
        self._alarm_sound_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._alarm_sound_combo.currentIndexChanged.connect(self._on_alarm_sound_changed)
        self._populate_sound_combo()
        alarm_row.addWidget(self._alarm_sound_combo, 1)

        alarm_row.addWidget(self._field_label("Default snooze"))
        self._snooze_combo = QComboBox()
        self._snooze_combo.setObjectName("settingsSnoozeCombo")
        self._snooze_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        for m in (5, 10, 15, 30):
            self._snooze_combo.addItem(f"{m} minutes", m)
        self._snooze_combo.currentIndexChanged.connect(self._on_snooze_changed)
        alarm_row.addWidget(self._snooze_combo, 1)

        root.addLayout(alarm_row)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setObjectName("settingsSep")
        root.addWidget(sep3)

        # ── Notifications (both toggles on one row) ─────────────────────────
        root.addWidget(self._section_title("Notifications"))

        notif_row = QHBoxLayout()
        notif_row.setContentsMargins(0, 0, 0, 8)
        notif_row.setSpacing(20)
        self._balloon_mail_chk = QCheckBox("Show balloon on new mail")
        self._balloon_mail_chk.setObjectName("settingsNotifyChk")
        self._balloon_mail_chk.stateChanged.connect(self._on_balloon_mail_changed)
        notif_row.addWidget(self._balloon_mail_chk)
        self._balloon_alarm_chk = QCheckBox("Show balloon on alarm")
        self._balloon_alarm_chk.setObjectName("settingsNotifyChk")
        self._balloon_alarm_chk.stateChanged.connect(self._on_balloon_alarm_changed)
        notif_row.addWidget(self._balloon_alarm_chk)
        notif_row.addStretch(1)
        root.addLayout(notif_row)

        root.addStretch()
        scroll.setWidget(panel)
        outer.addWidget(scroll)
        self._scroll = scroll

        self._update_theme_btn_icon()
        self._update_always_btn_icon()

    def _populate_sound_combo(self):
        self._alarm_sound_combo.blockSignals(True)
        self._alarm_sound_combo.clear()
        assets = Paths.assets_dir()
        wavs = sorted(p.name for p in assets.glob("*.wav") if p.is_file())
        if not wavs:
            wavs = ["alarm_event.wav", "calendar_event.wav", "email_event.wav"]
        current = get_alarm_sound_default()
        for w in wavs:
            self._alarm_sound_combo.addItem(w, w)
        idx = self._alarm_sound_combo.findData(current)
        if idx < 0:
            idx = 0
        self._alarm_sound_combo.setCurrentIndex(idx)
        self._alarm_sound_combo.blockSignals(False)

    def _load_from_settings(self):
        self._mail_enable_chk.blockSignals(True)
        self._mail_interval_spin.blockSignals(True)
        self._balloon_mail_chk.blockSignals(True)
        self._balloon_alarm_chk.blockSignals(True)
        self._startup_chk.blockSignals(True)
        self._snooze_combo.blockSignals(True)

        self._mail_enable_chk.setChecked(get_mail_awareness_enabled())
        self._mail_interval_spin.setValue(get_mail_poll_interval_minutes())
        self._balloon_mail_chk.setChecked(get_notify_balloon_new_mail())
        self._balloon_alarm_chk.setChecked(get_notify_balloon_alarm())
        self._startup_chk.setChecked(is_run_at_startup_enabled())

        dm = get_default_snooze_minutes()
        si = self._snooze_combo.findData(dm)
        if si < 0:
            si = self._snooze_combo.findData(10)
        self._snooze_combo.setCurrentIndex(max(0, si))

        self._mail_enable_chk.blockSignals(False)
        self._mail_interval_spin.blockSignals(False)
        self._balloon_mail_chk.blockSignals(False)
        self._balloon_alarm_chk.blockSignals(False)
        self._startup_chk.blockSignals(False)
        self._snooze_combo.blockSignals(False)

    def on_tab_activated(self):
        self._startup_chk.blockSignals(True)
        self._startup_chk.setChecked(is_run_at_startup_enabled())
        self._startup_chk.blockSignals(False)

    def _on_theme_clicked(self):
        toggle_theme_mode()
        persist_theme_mode(theme_mode())
        self._update_theme_btn_icon()
        self.apply_theme()
        self.appearance_changed.emit()

    def _on_always_clicked(self):
        self._always_on_top = not self._always_on_top
        set_always_on_top(self._always_on_top)
        self._update_always_btn_icon()
        self.apply_theme()
        self.appearance_changed.emit()

    def _update_theme_btn_icon(self):
        is_dark = theme_mode() == "dark"
        icon_name = "theme_dark.png" if is_dark else "theme_light.png"
        self._theme_btn.setIcon(QIcon(str(Paths.assets_dir() / icon_name)))
        self._theme_btn.setIconSize(QSize(16, 16))
        state = "Dark mode" if is_dark else "Light mode"
        self._theme_btn.setToolTip(f"Theme: {state} (click to toggle)")

    def _update_always_btn_icon(self):
        icon_name = "OnTop_on.png" if self._always_on_top else "OnTop_off.png"
        self._always_btn.setIcon(QIcon(str(Paths.assets_dir() / icon_name)))
        self._always_btn.setIconSize(QSize(16, 16))
        state = "On" if self._always_on_top else "Off"
        self._always_btn.setToolTip(f"Always on top: {state} (click to toggle)")

    def _on_mail_enable_changed(self, state: int):
        set_mail_awareness_enabled(bool(state))
        self.mail_settings_changed.emit()

    def _on_mail_interval_changed(self, value: int):
        set_mail_poll_interval_minutes(value)
        self.mail_settings_changed.emit()

    def _on_alarm_sound_changed(self):
        data = self._alarm_sound_combo.currentData()
        if data:
            set_alarm_sound_default(str(data))

    def _on_snooze_changed(self):
        m = self._snooze_combo.currentData()
        if m is not None:
            set_default_snooze_minutes(int(m))

    def _on_balloon_mail_changed(self, state: int):
        set_notify_balloon_new_mail(bool(state))

    def _on_balloon_alarm_changed(self, state: int):
        set_notify_balloon_alarm(bool(state))

    def _on_startup_changed(self, state: int):
        set_run_at_startup(bool(state))

    def apply_theme(self):
        spin_style = _spin_btn_style()
        for b in self._mail_interval_spin_btns:
            b.setStyleSheet(spin_style)

        self._always_on_top = get_always_on_top()
        self._update_theme_btn_icon()
        self._update_always_btn_icon()

        self.setStyleSheet(
            f"""
            QScrollArea {{
                background: {c("bg")};
                border: none;
            }}
            QWidget#settingsPanel {{
                background: {c("bg")};
                color: {c("text")};
            }}
            QLabel#settingsSectionTitle {{
                color: {c("accent")};
                font-size: 12px;
                font-weight: 600;
                padding: 14px 0 6px 0;
            }}
            QLabel#settingsFieldLbl {{
                color: {c("dim")};
                font-size: 11px;
            }}
            QFrame#settingsSep {{
                color: {c("border")};
                background: {c("border")};
                max-height: 1px;
                margin: 4px 0;
            }}
            QComboBox, QComboBox#settingsAlarmSoundCombo, QComboBox#settingsSnoozeCombo {{
                background: {c("bg")};
                color: {c("text")};
                border: 1px solid {c("action_btn_border")};
                border-radius: 4px;
                padding: 5px 8px;
                font-size: 11px;
                min-width: 96px;
            }}
            QComboBox QAbstractItemView {{
                background: {c("titlebar")};
                color: {c("text")};
                border: 1px solid {c("border")};
                selection-background-color: {c("accent")};
            }}
            QSpinBox#settingsMailIntervalSpin {{
                background: {c("bg")};
                color: {c("text")};
                border: 1px solid {c("action_btn_border")};
                border-radius: 4px;
                border-top-right-radius: 0;
                border-bottom-right-radius: 0;
                padding: 5px;
                font-size: 11px;
            }}
            QSpinBox#settingsMailIntervalSpin:focus {{
                border: 1px solid {c("accent")};
            }}
            QToolButton#themeToggle {{
                background: transparent;
                border: 1px solid {c("action_btn_border")};
                border-radius: 5px;
                padding: 3px;
            }}
            QToolButton#themeToggle:hover {{
                border: 1px solid {c("action_btn_border_hover")};
            }}
            QToolButton#alwaysOnTopToggle {{
                background: transparent;
                border: 1px solid {c("action_btn_border")};
                border-radius: 5px;
                padding: 3px;
            }}
            QToolButton#alwaysOnTopToggle:hover {{
                border: 1px solid {c("action_btn_border_hover")};
            }}
            QCheckBox#settingsMailEnableChk::indicator,
            QCheckBox#settingsNotifyChk::indicator,
            QCheckBox#settingsStartupChk::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid {c("action_btn_border")};
                background: {c("titlebar")};
            }}
            QCheckBox#settingsMailEnableChk::indicator:checked,
            QCheckBox#settingsNotifyChk::indicator:checked,
            QCheckBox#settingsStartupChk::indicator:checked {{
                background: {c("accent")};
                border-color: {c("accent")};
            }}
            QCheckBox#settingsNotifyChk, QCheckBox#settingsStartupChk {{
                color: {c("text")};
                font-size: 12px;
            }}
            """
        )
