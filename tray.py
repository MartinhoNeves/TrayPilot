"""
tray.py — QSystemTrayIcon: popup, full window, and alarm notifications.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QTimer, QUrl
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from alarm_notification import AlarmNotificationDialog
from alarm_scheduler import AlarmScheduler
from alarms import SOUND_ALARM, SOUND_EMAIL
from google_client import GoogleClient
from paths import Paths
from popup import PopupFlyout
from settings import get_alarm_sound_default
from window_main import MainWindow

if TYPE_CHECKING:
    from gmail_client import GmailClient


class TrayIcon(QObject):
    def __init__(
        self,
        app: QApplication,
        google_client: GoogleClient,
        alarm_scheduler: AlarmScheduler,
        gmail_client: "GmailClient | None" = None,
    ):
        super().__init__()
        self._app = app
        self._client = google_client
        self._alarm_scheduler = alarm_scheduler
        self._gmail = gmail_client
        self._window = None  # lazy-created on first open

        self._icon = QSystemTrayIcon(QIcon(str(Paths.assets_dir() / "app.ico")))
        self._icon.setToolTip("TrayPilot")
        self._single_click_timer = QTimer(self)
        self._single_click_timer.setSingleShot(True)
        self._single_click_timer.timeout.connect(self._open_popup)

        self._popup = PopupFlyout(google_client, gmail_client=gmail_client)
        self._alarm_dialog = AlarmNotificationDialog()
        self._alarm_dialog.dismiss_btn.clicked.connect(self._on_alarm_dismiss)
        self._alarm_dialog.snooze_btn.clicked.connect(self._on_alarm_snooze)
        self._audio_output = QAudioOutput(self)
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._audio_output)

        # Auto-refresh popup (and window if open) when service becomes ready
        self._client.ready.connect(self._on_client_ready)
        self._alarm_scheduler.alarm_fired.connect(self._on_alarm_fired)
        self._alarm_scheduler.alarms_changed.connect(self._on_alarms_changed)

        if self._gmail is not None:
            self._gmail.new_mail_detected.connect(self._on_new_mail)
            self._gmail.unread_count_changed.connect(self._on_unread_changed)

        self._build_menu()
        self._icon.activated.connect(self._on_activated)

    def show(self):
        self._icon.show()

    def _build_menu(self):
        menu = QMenu()

        for tab_name in ("Calendar", "Emails", "Alarms", "Settings", "About"):
            tab_action = QAction(tab_name, self)
            tab_action.triggered.connect(
                lambda _checked=False, t=tab_name.lower(): self._open_window_tab(t)
            )
            menu.addAction(tab_action)

        menu.addSeparator()
        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self._refresh)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._app.quit)

        menu.addAction(refresh_action)
        menu.addAction(quit_action)
        self._icon.setContextMenu(menu)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Delay single-click action so double-click can cancel it.
            self._single_click_timer.start(220)
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self._single_click_timer.isActive():
                self._single_click_timer.stop()
            self._open_window()

    def _open_popup(self):
        if self._popup.isVisible():
            self._popup.hide()
        else:
            self._popup.show_at_tray()

    def _open_window(self):
        if self._popup.isVisible():
            self._popup.hide()
        if self._window is None:
            self._window = MainWindow(
                self._client,
                alarm_scheduler=self._alarm_scheduler,
                gmail_client=self._gmail,
                on_theme_changed=self._on_theme_changed,
            )
        if self._window.isHidden():
            self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def _open_window_tab(self, tab_name: str):
        self._open_window()
        if self._window is not None:
            self._window.open_tab(tab_name)

    def _on_theme_changed(self):
        self._popup.apply_theme()
        self._alarm_dialog._apply_theme()
        if self._popup.isVisible():
            self._popup.refresh()

    def _on_client_ready(self):
        """Called when GoogleClient finishes building the Calendar service."""
        self._popup.refresh()
        # MainWindow connects to ready itself and refreshes when visible.

    def _refresh(self):
        self._client.refresh()
        self._alarm_scheduler.refresh()
        self._popup.refresh()
        if self._window is not None and self._window.isVisible():
            self._window.refresh()
        if self._gmail is not None:
            self._gmail.poll_now()

    def _on_new_mail(self, count: int):
        """Play mail sound and optionally show a tray balloon for new unread mail."""
        from settings import get_mail_awareness_enabled, get_notify_balloon_new_mail

        if not get_mail_awareness_enabled():
            return
        self._play_alarm_sound(SOUND_EMAIL)
        if not get_notify_balloon_new_mail():
            return
        noun = "message" if count == 1 else "messages"
        self._icon.showMessage(
            "New Mail",
            f"You have {count} unread {noun} in Gmail.",
            QSystemTrayIcon.MessageIcon.Information,
            6000,
        )

    def _on_unread_changed(self, count: int):
        """Update tray tooltip to reflect current unread count."""
        from settings import get_mail_awareness_enabled
        if not get_mail_awareness_enabled() or count == 0:
            self._icon.setToolTip("TrayPilot")
        else:
            noun = "message" if count == 1 else "messages"
            self._icon.setToolTip(f"TrayPilot — {count} unread {noun}")

    def _on_alarm_fired(self, alarm):
        from settings import get_notify_balloon_alarm

        if get_notify_balloon_alarm():
            self._icon.showMessage(
                "Alarm",
                alarm.title or "Alarm fired",
                QSystemTrayIcon.MessageIcon.Information,
                8000,
            )
        sound = getattr(alarm, "sound", "") or get_alarm_sound_default() or SOUND_ALARM
        self._play_alarm_sound(sound)
        self._alarm_dialog.present(alarm)

    def _on_alarm_dismiss(self):
        alarm_id = self._alarm_dialog.current_alarm_id()
        if alarm_id:
            self._alarm_scheduler.dismiss(alarm_id)
        self._alarm_dialog.hide()

    def _on_alarm_snooze(self):
        alarm_id = self._alarm_dialog.current_alarm_id()
        if alarm_id:
            self._alarm_scheduler.snooze(alarm_id, self._alarm_dialog.selected_snooze_minutes())
        self._alarm_dialog.hide()

    def _on_alarms_changed(self):
        if self._window is not None and self._window.isVisible():
            self._window.refresh_alarms()

    def _play_alarm_sound(self, filename: str):
        if not filename:
            return
        path = Path(Paths.assets_dir()) / filename
        if not path.exists():
            return
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        self._player.play()

