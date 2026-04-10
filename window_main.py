"""
window_main.py — Full QMainWindow (double-click from tray).
"""
from __future__ import annotations

import datetime
import re
from typing import TYPE_CHECKING

from PyQt6.QtCore import QDate, QObject, QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMainWindow, QSizePolicy, QStatusBar,
    QMessageBox, QTabWidget, QWidget,
)

from alarm_scheduler import AlarmScheduler
from alarms import (
    Alarm,
    RECURRENCE_NONE,
    create_alarm,
    delete_alarm,
    list_alarms,
    recalculate_linked_alarms,
    upsert_alarm,
)
from colour_theme import c
from google_client import GoogleClient, event_start_date, is_urgent
from panel_alarm_form import AlarmFormPanel
from paths import Paths
from settings import get_always_on_top, get_window_size, set_window_size
from panel_event_form import EventFormPanel
from widget_alarm_list import AlarmListWidget
from widget_calendar import CalendarWidget
from widget_email_stub import EmailStubWidget
from widget_event_list import EventListWidget
from widget_about import AboutTabWidget
from widget_settings import SettingsWidget

if TYPE_CHECKING:
    from gmail_client import GmailClient

GEOMETRY_MAIN_X_Y     = (780, 520)  # default (width, height)
GEOMETRY_MAIN_MIN_X_Y = (600, 420)  # minimum (width, height)
LEFT_PANEL_BASE_WIDTH = 320
FORM_WIDTH_MIN = 280


class _MonthFetchWorker(QObject):
    finished = pyqtSignal(object)

    def __init__(self, client: GoogleClient, start: datetime.datetime, end: datetime.datetime):
        super().__init__()
        self._client = client
        self._start = start
        self._end = end

    def run(self):
        events = self._client.get_events(self._start, self._end)
        self.finished.emit(events)


class MainWindow(QMainWindow):
    def __init__(
        self,
        google_client: GoogleClient,
        alarm_scheduler: AlarmScheduler,
        gmail_client: "GmailClient | None" = None,
        parent=None,
        on_theme_changed=None,
    ):
        super().__init__(parent)
        self._client = google_client
        self._alarm_scheduler = alarm_scheduler
        self._gmail = gmail_client
        self._on_theme_changed = on_theme_changed
        self._always_on_top = get_always_on_top()
        self._month_events: list[dict] = []
        self._active_filter_date: datetime.date | None = None
        self._last_client_error = ""
        self._month_fetch_thread: QThread | None = None
        self._month_fetch_worker: QObject | None = None
        self._month_fetch_request_id = 0
        self._tabs: QTabWidget | None = None
        self._calendar_tab_index = 0
        self._emails_tab_index = 1
        self._alarms_tab_index = 2  # Calendar=0, Emails=1, Alarms=2
        self._settings_tab_index = -1
        self._about_tab_index = -1
        self._snapping_calendar = False

        app_ver = ""
        app = QApplication.instance()
        if app is not None:
            app_ver = (app.applicationVersion() or "").strip()
        self.setWindowTitle(f"TrayPilot {app_ver}" if app_ver else "TrayPilot")
        self.setWindowIcon(QIcon(str(Paths.assets_dir() / "app.ico")))
        self.resize(*get_window_size())
        self.setMinimumSize(*GEOMETRY_MAIN_MIN_X_Y)
        self._apply_always_on_top()

        self._build_ui()
        self._apply_style()

        # Connect calendar month navigation → re-fetch
        self._calendar.currentPageChanged.connect(self._on_month_changed)
        self._calendar.clicked.connect(self._on_calendar_date_clicked)
        self._event_list.new_event_requested.connect(self._on_new_event_requested)
        self._event_list.today_requested.connect(self._on_today_requested)
        self._event_list.edit_requested.connect(self._on_edit_requested)
        self._event_list.delete_requested.connect(self._on_delete_requested)
        self._event_form.submit_requested.connect(self._on_form_submit)
        self._client.error.connect(self._on_client_error)
        self._alarm_list.add_requested.connect(self._on_alarm_new_requested)
        self._alarm_list.edit_requested.connect(self._on_alarm_edit_requested)
        self._alarm_list.delete_requested.connect(self._on_alarm_delete_requested)
        self._alarm_list.enabled_toggled.connect(self._on_alarm_enabled_toggled)
        self._alarm_form.submit_requested.connect(self._on_alarm_form_submit)
        self._alarm_scheduler.alarms_changed.connect(self.refresh_alarms)
        # Month fetch can run in showEvent before ensure_authenticated() finishes building
        # the API service; refetch as soon as the client becomes ready.
        self._client.ready.connect(self._on_google_service_ready)

    # ── Public ────────────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        self._center_on_screen()
        self._apply_nav_bounds()
        self._fetch_for_month(self._calendar.yearShown(), self._calendar.monthShown())
        # Load alarms from disk only — no network call on the main thread.
        # Full recalculation (with linked events) happens on explicit refresh.
        self._load_alarms_fast()

    def refresh(self):
        self._fetch_for_month(self._calendar.yearShown(), self._calendar.monthShown())
        self.refresh_alarms()

    def refresh_alarms(self):
        alarms = self._load_alarms_with_links()
        self._alarm_list.set_alarms(alarms)

    def open_tab(self, tab_name: str):
        if self._tabs is None:
            return
        key = tab_name.strip().lower()
        tab_map = {
            "calendar": self._calendar_tab_index,
            "emails": self._emails_tab_index,
            "email": self._emails_tab_index,
            "alarms": self._alarms_tab_index,
            "alarm": self._alarms_tab_index,
            "settings": self._settings_tab_index,
            "about": self._about_tab_index,
        }
        idx = tab_map.get(key)
        if idx is not None and idx >= 0:
            self._tabs.setCurrentIndex(idx)

    def _load_alarms_fast(self):
        """Load alarm list from disk without a network call. Used on first show."""
        alarms = list_alarms()
        self._alarm_list.set_alarms(alarms)

    def _on_google_service_ready(self):
        # ready is emitted from a plain threading.Thread, so PyQt6 treats it as
        # DirectConnection (not QueuedConnection). Post the refresh to the main
        # event loop via context=self so Qt routes it to the GUI thread.
        if self.isVisible():
            QTimer.singleShot(0, self, self.refresh)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Tab widget ────────────────────────────────────────────────────────
        tabs = QTabWidget()
        tabs.setObjectName("mainTabs")
        tabs.blockSignals(True)
        tabs.currentChanged.connect(self._on_tab_changed)

        # Calendar tab
        cal_page = QWidget()
        cal_layout = QHBoxLayout(cal_page)
        cal_layout.setContentsMargins(0, 0, 0, 0)
        cal_layout.setSpacing(0)

        self._left_panel = QWidget()
        self._left_panel.setMinimumWidth(LEFT_PANEL_BASE_WIDTH)
        self._left_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        left_layout = QHBoxLayout(self._left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self._event_list = EventListWidget(self._client)
        self._event_list.setMinimumWidth(LEFT_PANEL_BASE_WIDTH)
        self._event_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._event_form = EventFormPanel(self._client)
        self._event_form.width_changed.connect(self._on_form_width_changed)
        left_layout.addWidget(self._event_list, 1)
        left_layout.addWidget(self._event_form)

        self._calendar = CalendarWidget()
        self._calendar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        cal_layout.addWidget(self._left_panel)

        # Vertical separator
        self._split_sep = QWidget()
        self._split_sep.setObjectName("splitSep")
        self._split_sep.setFixedWidth(1)
        cal_layout.addWidget(self._split_sep)

        cal_layout.addWidget(self._calendar, 1)
        # Agenda+form column vs month calendar: equal width (also when slide-in form is closed).
        cal_layout.setStretch(0, 50)
        cal_layout.setStretch(2, 50)

        self._calendar_tab_index = tabs.addTab(cal_page, "📅  Calendar")

        # Emails tab (between Calendar and Alarms)
        self._email_stub = EmailStubWidget(self._gmail)
        self._emails_tab_index = tabs.addTab(self._email_stub, "📧  Emails")

        # Alarms tab
        alarms_page = QWidget()
        alarms_layout = QHBoxLayout(alarms_page)
        alarms_layout.setContentsMargins(0, 0, 0, 0)
        alarms_layout.setSpacing(0)
        self._alarm_list = AlarmListWidget()
        self._alarm_list.setMinimumWidth(LEFT_PANEL_BASE_WIDTH)
        self._alarm_form = AlarmFormPanel()
        self._alarm_form.width_changed.connect(self._on_alarm_form_width_changed)
        alarms_layout.addWidget(self._alarm_list, 1)
        alarms_layout.addWidget(self._alarm_form)
        self._alarms_tab_index = tabs.addTab(alarms_page, "⏰  Alarms")

        self._settings_widget = SettingsWidget(self._gmail)
        self._settings_widget.appearance_changed.connect(self._on_settings_appearance)
        self._settings_widget.mail_settings_changed.connect(self._on_settings_mail)
        self._settings_tab_index = tabs.addTab(self._settings_widget, "⚙  Settings")

        self._about_widget = AboutTabWidget()
        self._about_tab_index = tabs.addTab(self._about_widget, "ℹ  About")

        tabs.blockSignals(False)
        self._tabs = tabs
        self.setCentralWidget(tabs)

        # ── Status bar ────────────────────────────────────────────────────────
        sb = QStatusBar()
        sb.setObjectName("mainStatusBar")
        sb.setSizeGripEnabled(False)
        self.setStatusBar(sb)

        # Left: connection status
        self._status_lbl = QLabel()
        self._status_lbl.setObjectName("statusLbl")
        sb.addWidget(self._status_lbl)

        # Right: last sync time
        self._sync_lbl = QLabel()
        self._sync_lbl.setObjectName("syncLbl")
        sb.addPermanentWidget(self._sync_lbl)

        self._set_status_connected(connected=False)

    def _apply_style(self):
        self.setStyleSheet(f"""
            QMainWindow {{
                background: {c("bg")};
            }}
            QWidget {{
                background: {c("bg")};
                color: {c("text")};
                font-family: 'Segoe UI', sans-serif;
            }}
            QWidget#splitSep {{
                background: {c("border")};
            }}
            QTabWidget#mainTabs::pane {{
                border: none;
                background: {c("bg")};
            }}
            QTabWidget#mainTabs > QTabBar {{
                background: {c("titlebar")};
            }}
            QTabBar::tab {{
                background: {c("titlebar")};
                color: {c("dim")};
                padding: 9px 18px;
                border: none;
                font-size: 12px;
                border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:selected {{
                color: {c("accent")};
                border-bottom: 2px solid {c("accent")};
            }}
            QTabBar::tab:hover:!selected {{
                color: {c("tab_hover")};
            }}
            QStatusBar#mainStatusBar {{
                background: {c("titlebar")};
                border-top: 1px solid {c("border")};
            }}
            QStatusBar#mainStatusBar::item {{
                border: none;
            }}
            QLabel#statusLbl, QLabel#syncLbl {{
                font-size: 10px;
                color: {c("dim")};
                background: transparent;
                padding: 0 4px;
            }}
        """)

    # ── Data ──────────────────────────────────────────────────────────────────

    def _fetch_for_month(self, year: int, month: int):
        first = datetime.date(year, month, 1)
        # Google Calendar timeMax is exclusive — use first instant of next month (UTC).
        if month == 12:
            next_month = datetime.date(year + 1, 1, 1)
        else:
            next_month = datetime.date(year, month + 1, 1)

        start = datetime.datetime(
            first.year, first.month, first.day, tzinfo=datetime.timezone.utc
        )
        end = datetime.datetime(
            next_month.year, next_month.month, next_month.day,
            tzinfo=datetime.timezone.utc,
        )

        self._month_fetch_request_id += 1
        req_id = self._month_fetch_request_id
        self._stop_month_fetch_thread()
        worker = _MonthFetchWorker(self._client, start, end)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        self._month_fetch_worker = worker

        def _on_finished(events):
            if req_id != self._month_fetch_request_id:
                return
            self._month_events = events
            if (
                self._active_filter_date is not None
                and (self._active_filter_date.year != year or self._active_filter_date.month != month)
            ):
                self._active_filter_date = None
            self._apply_event_filter()

            event_dates: set[datetime.date] = set()
            urgent_dates: set[datetime.date] = set()
            for evt in events:
                dt_evt = event_start_date(evt)
                if dt_evt is not None:
                    d = dt_evt.date()
                    if is_urgent(evt):
                        urgent_dates.add(d)
                    else:
                        event_dates.add(d)
            self._calendar.set_event_dates(event_dates, urgent_dates)
            self._set_status_connected(connected=self._client.is_ready)
            self._month_fetch_worker = None
            thread.quit()

        worker.finished.connect(_on_finished)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_month_fetch_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._month_fetch_thread = thread
        thread.start()

    def _stop_month_fetch_thread(self):
        thread = self._month_fetch_thread
        if thread is None:
            return
        try:
            running = thread.isRunning()
        except RuntimeError:
            self._month_fetch_thread = None
            self._month_fetch_worker = None
            return
        if running:
            thread.quit()
            thread.wait(150)
        self._month_fetch_thread = None
        self._month_fetch_worker = None

    def _on_month_fetch_thread_finished(self):
        self._month_fetch_thread = None
        self._month_fetch_worker = None

    def _on_month_changed(self, year: int, month: int):
        if self._snapping_calendar:
            return
        min_page = self._nav_min()
        max_page = self._nav_max()
        if (year, month) < min_page:
            self._snap_calendar(*min_page, direction="past")
            return
        if (year, month) > max_page:
            self._snap_calendar(*max_page, direction="future")
            return
        self._apply_nav_bounds()
        self._fetch_for_month(year, month)

    # ── Navigation bounds ─────────────────────────────────────────────────────

    @staticmethod
    def _nav_min() -> tuple[int, int]:
        """One month before today (computed fresh each call, safe across midnight)."""
        today = datetime.date.today()
        if today.month == 1:
            return today.year - 1, 12
        return today.year, today.month - 1

    @staticmethod
    def _nav_max() -> tuple[int, int]:
        """One year (12 months) ahead of today."""
        today = datetime.date.today()
        m = today.month + 12
        return today.year + (m - 1) // 12, (m - 1) % 12 + 1

    def _apply_nav_bounds(self):
        min_year, min_month = self._nav_min()
        max_year, max_month = self._nav_max()
        self._calendar.set_nav_bounds(min_year, min_month, max_year, max_month)

    def _snap_calendar(self, year: int, month: int, direction: str):
        self._snapping_calendar = True
        self._calendar.setCurrentPage(year, month)
        self._snapping_calendar = False
        self._apply_nav_bounds()
        if direction == "past":
            msg = (
                "TrayPilot only shows up to 1 month in the past.\n\n"
                "To browse further back, please open Google Calendar."
            )
        else:
            msg = (
                "TrayPilot only shows up to 1 year ahead.\n\n"
                "To browse further forward, please open Google Calendar."
            )
        QMessageBox.information(self, "Navigation limit reached", msg)

    def _on_calendar_date_clicked(self, qdate):
        clicked_date = datetime.date(qdate.year(), qdate.month(), qdate.day())

        # CAL-03: clicking selected date again clears the active filter
        if self._active_filter_date == clicked_date:
            self._active_filter_date = None
        else:
            # CAL-02: clicking a date filters the agenda list to that day
            self._active_filter_date = clicked_date

        self._apply_event_filter()

    def _apply_event_filter(self):
        if self._active_filter_date is None:
            filtered = self._month_events
        else:
            filtered = [
                evt for evt in self._month_events
                if (dt := event_start_date(evt)) is not None and dt.date() == self._active_filter_date
            ]
        self._event_list.set_filter_date(self._active_filter_date)
        self._event_list.load_events(filtered)

    def _on_new_event_requested(self):
        selected = self._calendar.selectedDate()
        selected_date = datetime.date(selected.year(), selected.month(), selected.day())
        self._event_form.open_for_new(selected_date, self._desired_form_width())

    def _on_today_requested(self):
        today = datetime.date.today()
        self._calendar.setCurrentPage(today.year, today.month)
        self._calendar.setSelectedDate(QDate(today.year, today.month, today.day))

    def _on_edit_requested(self, event: dict):
        self._event_form.open_for_edit(event, self._desired_form_width())

    def _on_delete_requested(self, event: dict):
        event_id = event.get("id")
        if not event_id:
            QMessageBox.warning(self, "Delete event", "Selected event has no ID.")
            return

        title = event.get("summary") or "(No title)"
        is_recurring_instance = bool(event.get("recurringEventId"))

        if not is_recurring_instance:
            response = QMessageBox.question(
                self,
                "Delete event",
                f"Delete '{title}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if response != QMessageBox.StandardButton.Yes:
                return
            deleted = self._client.delete_event(event_id)
            if not deleted:
                QMessageBox.warning(
                    self,
                    "Delete failed",
                    self._last_client_error or "Could not delete event.",
                )
                return
            self.refresh()
            return

        action = self._ask_recurring_delete_scope(title)
        if action == "cancel":
            return
        if action == "this":
            deleted = self._client.delete_event(event_id)
        elif action == "all":
            series_id = str(event.get("recurringEventId") or "")
            deleted = self._client.delete_event(series_id) if series_id else False
        else:  # this_and_following
            deleted = self._delete_this_and_following(event)

        if not deleted:
            QMessageBox.warning(
                self,
                "Delete failed",
                self._last_client_error or "Could not delete event.",
            )
            return
        self.refresh()

    def _on_form_submit(self, event_id, payload: dict):
        if event_id:
            ok = self._client.update_event(event_id, payload)
            if ok is None:
                self._event_form.show_error(self._last_client_error or "Could not update event.")
                return
        else:
            ok = self._client.create_event(payload)
            if ok is None:
                self._event_form.show_error(self._last_client_error or "Could not create event.")
                return

        self._event_form.close_panel()
        self.refresh()

    def _on_client_error(self, message: str):
        self._last_client_error = message

    def _on_form_width_changed(self, width: int):
        w = int(width)
        self._left_panel.setMinimumWidth(LEFT_PANEL_BASE_WIDTH + max(0, w))

    def _on_alarm_form_width_changed(self, _width: int):
        pass

    def _ask_recurring_delete_scope(self, title: str) -> str:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Delete recurring event")
        box.setText(f"'{title}' is part of a recurring series.")
        box.setInformativeText("Choose what to delete:")

        this_btn = box.addButton("This event only", QMessageBox.ButtonRole.AcceptRole)
        following_btn = box.addButton("This and following", QMessageBox.ButtonRole.DestructiveRole)
        all_btn = box.addButton("All events in series", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton(QMessageBox.StandardButton.Cancel)

        box.exec()
        clicked = box.clickedButton()
        if clicked is this_btn:
            return "this"
        if clicked is following_btn:
            return "this_and_following"
        if clicked is all_btn:
            return "all"
        if clicked is cancel_btn:
            return "cancel"
        return "cancel"

    def _delete_this_and_following(self, event: dict) -> bool:
        series_id = str(event.get("recurringEventId") or "")
        if not series_id:
            return False
        master = self._client.get_event(series_id)
        if not master:
            return False

        recurrence = master.get("recurrence") or []
        target_start = self._event_instance_start(event)
        if target_start is None:
            return False
        until_dt = (target_start.astimezone(datetime.timezone.utc) - datetime.timedelta(seconds=1))
        until_token = until_dt.strftime("%Y%m%dT%H%M%SZ")

        updated_rules: list[str] = []
        for rule in recurrence:
            if not isinstance(rule, str) or not rule.startswith("RRULE:"):
                updated_rules.append(rule)
                continue
            body = rule[len("RRULE:"):]
            body = re.sub(r";UNTIL=[^;]+", "", body)
            body = re.sub(r";COUNT=\d+", "", body)
            body = f"{body};UNTIL={until_token}"
            updated_rules.append(f"RRULE:{body}")

        if not updated_rules:
            return False

        updated = self._client.update_event(series_id, {"recurrence": updated_rules})
        return updated is not None

    def _event_instance_start(self, event: dict) -> datetime.datetime | None:
        start = event.get("start") or {}
        if "dateTime" in start:
            try:
                dt_val = datetime.datetime.fromisoformat(str(start["dateTime"]))
                if dt_val.tzinfo is None:
                    dt_val = dt_val.replace(tzinfo=datetime.datetime.now().astimezone().tzinfo)
                return dt_val
            except Exception:
                return None
        if "date" in start:
            try:
                day = datetime.date.fromisoformat(str(start["date"]))
                local_tz = datetime.datetime.now().astimezone().tzinfo
                return datetime.datetime.combine(day, datetime.time.min, tzinfo=local_tz)
            except Exception:
                return None
        return None

    def _on_tab_changed(self, index: int):
        if index == self._alarms_tab_index:
            self.refresh_alarms()
        elif index == self._settings_tab_index:
            self._settings_widget.on_tab_activated()
        elif index == self._about_tab_index:
            self._about_widget.on_tab_activated()

    def _desired_form_width(self) -> int:
        # Make the slide form occupy about half of the agenda area.
        return max(FORM_WIDTH_MIN, int(self._left_panel.width() * 0.50))

    def _desired_alarm_form_width(self) -> int:
        return max(FORM_WIDTH_MIN, int(self.width() * 0.50))

    def _load_alarms_with_links(self) -> list[Alarm]:
        alarms = list_alarms()
        now = datetime.datetime.now().astimezone()
        start = now - datetime.timedelta(days=365)
        end = now + datetime.timedelta(days=365)
        events = self._client.get_events(start, end) if self._client.is_ready else []
        alarms = recalculate_linked_alarms(alarms, events)
        self._alarm_form.set_calendar_events(events)
        return alarms

    def _on_alarm_new_requested(self):
        self._alarm_form.open_for_new(width=self._desired_alarm_form_width())

    def _on_alarm_edit_requested(self, alarm: Alarm):
        self._alarm_form.open_for_edit(alarm, width=self._desired_alarm_form_width())

    def _on_alarm_delete_requested(self, alarm: Alarm):
        response = QMessageBox.question(
            self,
            "Delete alarm",
            f"Delete '{alarm.title}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return
        delete_alarm(alarm.id)
        self._alarm_form.close_panel()
        self._alarm_scheduler.refresh()

    def _on_alarm_enabled_toggled(self, alarm_id: str, enabled: bool):
        alarms = list_alarms()
        for alarm in alarms:
            if alarm.id == alarm_id:
                alarm.enabled = enabled
                upsert_alarm(alarm)
                break
        self._alarm_scheduler.refresh()

    def _on_alarm_form_submit(self, alarm_id, payload: dict):
        if alarm_id:
            alarm = next((a for a in list_alarms() if a.id == alarm_id), None)
            if alarm is None:
                self._alarm_form.close_panel()
                return
            alarm.title = payload["title"]
            alarm.next_fire_iso = payload["next_fire_iso"]
            alarm.recurrence = payload["recurrence"] or RECURRENCE_NONE
            alarm.sound = payload["sound"]
            alarm.linked_event_id = payload["linked_event_id"]
            alarm.linked_offset_minutes = int(payload["linked_offset_minutes"])
            upsert_alarm(alarm)
        else:
            create_alarm(
                title=payload["title"],
                next_fire=datetime.datetime.fromisoformat(payload["next_fire_iso"]),
                recurrence=payload["recurrence"] or RECURRENCE_NONE,
                sound=payload["sound"],
                linked_event_id=payload["linked_event_id"],
                linked_offset_minutes=int(payload["linked_offset_minutes"]),
            )
        self._alarm_form.close_panel()
        self._alarm_scheduler.refresh()

    # ── Status bar helpers ────────────────────────────────────────────────────

    def _set_status_connected(self, connected: bool):
        now_str = datetime.datetime.now().strftime("%H:%M")
        if connected:
            self._status_lbl.setText("⬤  Connected to Google Calendar")
            self._status_lbl.setStyleSheet(
                f"font-size: 10px; color: {c('status_connected')}; background: transparent; padding: 0 4px;"
            )
            self._sync_lbl.setText(f"Last sync: {now_str}")
        else:
            self._status_lbl.setText("◯  Connecting…")
            self._status_lbl.setStyleSheet(
                f"font-size: 10px; color: {c('dim')}; background: transparent; padding: 0 4px;"
            )
            self._sync_lbl.setText("")

    def _on_settings_appearance(self):
        self._always_on_top = get_always_on_top()
        self._apply_always_on_top()
        self._apply_style()
        self._settings_widget.apply_theme()
        self._about_widget.apply_theme()
        self._event_list.apply_theme()
        self._calendar.apply_theme()
        self._event_form.apply_theme()
        self._alarm_list.apply_theme()
        self._alarm_form.apply_theme()
        self._email_stub.apply_theme()
        self.refresh()
        self._set_status_connected(connected=self._client.is_ready)
        if callable(self._on_theme_changed):
            self._on_theme_changed()

    def _on_settings_mail(self):
        from settings import get_mail_awareness_enabled, get_mail_poll_interval_minutes

        if self._gmail is None:
            return
        if get_mail_awareness_enabled():
            self._gmail.start_polling(get_mail_poll_interval_minutes())
        else:
            self._gmail.stop_polling()

    def _apply_always_on_top(self):
        was_visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self._always_on_top)
        if was_visible:
            self.show()
            self.raise_()
            self.activateWindow()

    def _center_on_screen(self):
        screen = self.screen()
        if screen is None:
            return
        area = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(area.center())
        self.move(frame.topLeft())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        size = event.size()
        set_window_size(size.width(), size.height())
        self._event_form.set_open_width(self._desired_form_width())
        self._alarm_form.set_open_width(self._desired_alarm_form_width())
