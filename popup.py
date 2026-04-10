"""
popup.py — Frameless flyout panel (single-click from tray).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from PyQt6.QtCore import QEvent, QObject, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFontMetrics
from PyQt6.QtWidgets import (
    QApplication, QFrame, QGraphicsDropShadowEffect,
    QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget, QSizePolicy,
)

from widget_email_row import EmailRow

from colour_theme import c
from alarms import Alarm, list_alarms
from google_client import (
    GoogleClient, event_color, event_start_date, event_start_display, is_urgent,
)

if TYPE_CHECKING:
    from gmail_client import GmailClient

GEOMETRY_POPUP_X_Y = (400, 660)  # (fixed_width, fixed_height)
_MAIL_ROWS_VISIBLE = 5           # number of email rows visible without scrolling
_ALARM_ROWS_VISIBLE = 5          # number of alarm rows visible without scrolling


class _EventCard(QWidget):
    """Single event row with hover highlight."""

    def enterEvent(self, event):
        self.setObjectName("eventCard_h")
        self.setStyleSheet(f"QWidget#eventCard_h {{ background: {c('row_hover_bg')}; }}")

    def leaveEvent(self, event):
        self.setObjectName("eventCard")
        self.setStyleSheet("QWidget#eventCard { background: transparent; }")


class _PopupFetchWorker(QObject):
    finished = pyqtSignal(object)  # payload dict

    def __init__(self, client: GoogleClient, view_date: date):
        super().__init__()
        self._client = client
        self._view_date = view_date

    def run(self):
        active_alarms = [a for a in list_alarms() if a.enabled][:5]
        if not self._client.is_ready:
            self.finished.emit(
                {
                    "ready": False,
                    "view_date": self._view_date,
                    "day_events": [],
                    "urgent_events": [],
                    "active_alarms": active_alarms,
                }
            )
            return
        now_local = datetime.now().astimezone()
        local_tz = now_local.tzinfo
        midnight = datetime.combine(self._view_date, datetime.min.time(), tzinfo=local_tz)
        day_start = midnight.astimezone(timezone.utc)
        day_end = (midnight + timedelta(days=1)).astimezone(timezone.utc)
        future_end = (midnight + timedelta(days=31)).astimezone(timezone.utc)
        day_events = self._client.get_events(day_start, day_end)
        future_all = self._client.get_events(day_start, future_end)
        urgent_events = [e for e in future_all if is_urgent(e)]
        self.finished.emit(
            {
                "ready": True,
                "view_date": self._view_date,
                "day_events": day_events,
                "urgent_events": urgent_events,
                "active_alarms": active_alarms,
            }
        )


class PopupFlyout(QWidget):

    def __init__(
        self,
        google_client: GoogleClient,
        gmail_client: "GmailClient | None" = None,
        parent=None,
    ):
        super().__init__(parent)
        self._client = google_client
        self._gmail = gmail_client
        self._view_date = datetime.now().date()
        self._fetch_thread: QThread | None = None
        self._fetch_worker: QObject | None = None
        self._fetch_request_id = 0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(*GEOMETRY_POPUP_X_Y)

        self._build_ui()
        self.apply_theme()

        if self._gmail is not None:
            self._gmail.messages_changed.connect(self._update_mail_section)

    # ── Public ────────────────────────────────────────────────────────────────

    def show_at_tray(self):
        self.apply_theme()
        self._start_populate_async()
        self._reposition()
        self.show()
        self.activateWindow()
        self.raise_()

    def refresh(self):
        if self.isVisible():
            self._start_populate_async()
            self._reposition()

    # ── Qt overrides ──────────────────────────────────────────────────────────

    def changeEvent(self, event):
        if event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow() and self.isVisible():
                self.hide()
        super().changeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_section_heights()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(0)

        self._container = QWidget()
        self._container.setObjectName("popup_container")

        shadow = QGraphicsDropShadowEffect(self._container)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(c("popup_shadow")))
        self._container.setGraphicsEffect(shadow)

        outer.addWidget(self._container)

        main = QVBoxLayout(self._container)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────────
        self._header = QWidget()
        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(16, 14, 16, 12)
        hl.setSpacing(0)

        self._date_lbl = QLabel()
        self._date_lbl.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {c('accent')}; background: transparent;"
        )
        hl.addWidget(self._date_lbl)
        hl.addStretch()

        self._refresh_btn = QPushButton("⟳")
        self._refresh_btn.setFixedSize(24, 24)
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.clicked.connect(self._on_refresh)
        hl.addWidget(self._refresh_btn)

        main.addWidget(self._header)

        # ── Scroll area ───────────────────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._body = QWidget()
        self._body.setStyleSheet(f"background: {c('bg')};")
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(0)
        self._scroll.setWidget(self._body)
        self._scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        main.addWidget(self._scroll)

        # ── Mail section (shown when awareness is enabled) ────────────────────
        self._mail_section = QWidget()
        self._mail_section.setObjectName("popupMailSection")
        ms_layout = QVBoxLayout(self._mail_section)
        ms_layout.setContentsMargins(0, 0, 0, 0)
        ms_layout.setSpacing(0)

        # Section separator
        self._mail_sep = QWidget()
        self._mail_sep.setFixedHeight(1)
        ms_layout.addWidget(self._mail_sep)

        # Section header
        mail_hdr = QWidget()
        mhl = QHBoxLayout(mail_hdr)
        mhl.setContentsMargins(16, 8, 16, 6)
        mhl.setSpacing(6)
        self._mail_hdr_lbl = QLabel("✉  UNREAD MAIL")
        self._mail_count_lbl = QLabel("")
        mhl.addWidget(self._mail_hdr_lbl)
        mhl.addWidget(self._mail_count_lbl)
        mhl.addStretch()
        ms_layout.addWidget(mail_hdr)

        # Scrollable rows (5 rows visible without scroll)
        self._mail_scroll = QScrollArea()
        self._mail_scroll.setWidgetResizable(True)
        self._mail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._mail_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._mail_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._mail_list = QWidget()
        self._mail_list_layout = QVBoxLayout(self._mail_list)
        self._mail_list_layout.setContentsMargins(0, 0, 0, 0)
        self._mail_list_layout.setSpacing(0)
        self._mail_list_layout.addStretch()
        self._mail_scroll.setWidget(self._mail_list)
        ms_layout.addWidget(self._mail_scroll, 1)

        self._mail_rows: list[EmailRow] = []
        self._mail_section.setVisible(False)
        self._mail_section.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        main.addWidget(self._mail_section)

        # ── Active alarms section (always shown below mail list) ──────────────
        self._alarms_section = QWidget()
        self._alarms_section.setObjectName("popupAlarmsSection")
        a_layout = QVBoxLayout(self._alarms_section)
        a_layout.setContentsMargins(0, 0, 0, 0)
        a_layout.setSpacing(0)

        self._alarms_sep = QWidget()
        self._alarms_sep.setFixedHeight(1)
        a_layout.addWidget(self._alarms_sep)

        alarms_hdr = QWidget()
        ahl = QHBoxLayout(alarms_hdr)
        ahl.setContentsMargins(16, 8, 16, 6)
        ahl.setSpacing(6)
        self._alarms_hdr_lbl = QLabel("⏰  ACTIVE ALARMS")
        self._alarms_count_lbl = QLabel("")
        ahl.addWidget(self._alarms_hdr_lbl)
        ahl.addWidget(self._alarms_count_lbl)
        ahl.addStretch()
        a_layout.addWidget(alarms_hdr)

        self._alarms_list = QWidget()
        self._alarms_list_layout = QVBoxLayout(self._alarms_list)
        self._alarms_list_layout.setContentsMargins(0, 0, 0, 0)
        self._alarms_list_layout.setSpacing(0)
        self._alarms_list_layout.addStretch()
        a_layout.addWidget(self._alarms_list, 1)

        self._alarms_section.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        main.addWidget(self._alarms_section)

        # ── Footer day navigation ─────────────────────────────────────────────
        self._footer = QWidget()
        fl = QHBoxLayout(self._footer)
        fl.setContentsMargins(16, 10, 16, 12)
        fl.setSpacing(8)

        self._prev_event_btn = QPushButton("← Previous Event")
        self._prev_event_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._prev_event_btn.clicked.connect(self._on_prev_event)
        fl.addWidget(self._prev_event_btn)

        self._today_btn = QPushButton("Today")
        self._today_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._today_btn.clicked.connect(self._on_today)
        fl.addWidget(self._today_btn)

        self._next_event_btn = QPushButton("Next Event →")
        self._next_event_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_event_btn.clicked.connect(self._on_next_event)
        fl.addWidget(self._next_event_btn)

        main.addWidget(self._footer)
        self._apply_section_heights()

    # ── Content ───────────────────────────────────────────────────────────────

    def _populate(self, payload: dict):
        # Clear body
        while self._body_layout.count():
            item = self._body_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Update date label
        self._date_lbl.setText(self._header_date_text(self._view_date))

        # Service not yet ready — show loading state
        if not payload.get("ready", False):
            loading = QLabel("Reading events from calendar…")
            loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
            loading.setStyleSheet(
                f"color: {c('dim')}; font-size: 12px; font-style: italic;"
                f" padding: 24px 16px; background: {c('bg')};"
            )
            self._body_layout.addWidget(loading)
            self._body_layout.addStretch()
            return

        day_events = payload.get("day_events", [])
        urgent_events = payload.get("urgent_events", [])
        active_alarms = payload.get("active_alarms", [])

        # Selected-day section
        self._body_layout.addWidget(self._section_label("Selected Day Events"))
        if day_events:
            for evt in day_events:
                self._body_layout.addWidget(self._event_card(evt, date_mode=False))
        else:
            self._body_layout.addWidget(self._muted_label("No events for this day"))

        # Urgent section
        self._body_layout.addWidget(self._urgent_divider())
        if urgent_events:
            for evt in urgent_events:
                self._body_layout.addWidget(self._event_card(evt, date_mode=True))
        else:
            self._body_layout.addWidget(self._muted_label("No urgent events"))

        self._body_layout.addStretch()
        self._update_alarms_section(active_alarms)

    # ── Widget builders ───────────────────────────────────────────────────────

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 600; color: {c('accent')};"
            f" padding: 10px 16px 6px; background: {c('bg')};"
        )
        return lbl

    def _muted_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {c('muted')}; font-size: 12px; font-style: italic;"
            f" padding: 4px 16px 8px; background: {c('bg')};"
        )
        return lbl

    def _event_card(self, event: dict, *, date_mode: bool) -> QWidget:
        card = _EventCard()
        card.setObjectName("eventCard")
        card.setStyleSheet("QWidget#eventCard { background: transparent; }")
        card.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 7, 16, 7)
        layout.setSpacing(10)

        # Color dot
        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background: {event_color(event)}; border-radius: 4px;")
        layout.addWidget(dot)

        # Time / date column
        if date_mode:
            dt = event_start_date(event)
            time_str = f"{dt.day} {dt.strftime('%b')}" if dt else ""
        else:
            time_str = event_start_display(event)

        time_lbl = QLabel(time_str)
        time_lbl.setFixedWidth(82)
        time_lbl.setStyleSheet(f"font-size: 11px; color: {c('dim')}; background: transparent;")
        layout.addWidget(time_lbl)

        # Title (elided to fit) — width scales with popup: total - shadow(16) - padding(32) - dot+time+spacing(70) - slack(22)
        title_raw = event.get("summary") or "(No title)"
        fm = QFontMetrics(QApplication.font())
        title_str = fm.elidedText(title_raw, Qt.TextElideMode.ElideRight, self.width() - 140)
        title_lbl = QLabel(title_str)
        title_lbl.setStyleSheet(f"font-size: 13px; color: {c('text')}; background: transparent;")
        layout.addWidget(title_lbl, 1)

        return card

    def _urgent_divider(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {c('bg')};")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(16, 10, 16, 6)
        layout.setSpacing(8)

        def _line() -> QWidget:
            f = QWidget()
            f.setFixedHeight(1)
            f.setStyleSheet(f"background: {c('popup_line_danger')};")
            return f

        layout.addWidget(_line())

        lbl = QLabel("⚠ Urgent — next 30 days")
        lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 600; color: {c('danger')}; background: transparent;"
        )
        layout.addWidget(lbl)

        layout.addWidget(_line())
        return w

    def _alarm_card(self, alarm: Alarm) -> QWidget:
        card = _EventCard()
        card.setObjectName("eventCard")
        card.setStyleSheet("QWidget#eventCard { background: transparent; }")

        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 7, 16, 7)
        layout.setSpacing(10)

        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background: {c('accent')}; border-radius: 4px;")
        layout.addWidget(dot)

        time_lbl = QLabel(f"{alarm.next_fire.strftime('%d %b')}\n{alarm.next_fire.strftime('%H:%M')}")
        time_lbl.setFixedWidth(46)
        time_lbl.setStyleSheet(f"font-size: 10px; color: {c('dim')}; background: transparent;")
        layout.addWidget(time_lbl)

        fm = QFontMetrics(QApplication.font())
        title_str = fm.elidedText(alarm.title or "Alarm", Qt.TextElideMode.ElideRight, self.width() - 140)
        title_lbl = QLabel(title_str)
        title_lbl.setStyleSheet(f"font-size: 13px; color: {c('text')}; background: transparent;")
        layout.addWidget(title_lbl, 1)
        return card

    def _update_alarms_section(self, alarms: list[Alarm]):
        while self._alarms_list_layout.count() > 1:
            item = self._alarms_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        visible_alarms = [a for a in alarms if a.enabled][:_ALARM_ROWS_VISIBLE]
        noun = "alarm" if len(visible_alarms) == 1 else "alarms"
        self._alarms_count_lbl.setText(f"{len(visible_alarms)} {noun}" if visible_alarms else "")

        if not visible_alarms:
            empty = QLabel("No active alarms")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setFixedHeight(EmailRow.ROW_HEIGHT)
            empty.setStyleSheet(
                f"color: {c('muted')}; font-size: 11px; font-style: italic; background: transparent;"
            )
            self._alarms_list_layout.insertWidget(0, empty)
            self._apply_alarm_section_theme()
            return

        for i, alarm in enumerate(visible_alarms):
            self._alarms_list_layout.insertWidget(i, self._alarm_card(alarm))
        self._apply_alarm_section_theme()

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_refresh(self):
        self._client.refresh()
        self._start_populate_async()
        self._reposition()

    def _on_prev_event(self):
        target = self._find_prev_event_date()
        if target is not None:
            self._view_date = target
        self._start_populate_async()

    def _on_today(self):
        self._view_date = datetime.now().date()
        self._start_populate_async()

    def _on_next_event(self):
        target = self._find_next_event_date()
        if target is not None:
            self._view_date = target
        self._start_populate_async()

    def _header_date_text(self, d: date) -> str:
        today = datetime.now().date()
        if d == today:
            return f"📅 Today, {d.strftime('%A')} {d.day} {d.strftime('%b')}"
        return f"📅 {d.strftime('%A')} {d.day} {d.strftime('%b')} {d.year}"

    def _find_prev_event_date(self) -> date | None:
        now_local = datetime.now().astimezone()
        local_tz = now_local.tzinfo
        day_start = datetime.combine(self._view_date, datetime.min.time(), tzinfo=local_tz)
        search_start = (day_start - timedelta(days=365)).astimezone(timezone.utc)
        search_end = day_start.astimezone(timezone.utc)
        events = self._client.get_events(search_start, search_end)
        event_dates = [
            dt.date()
            for evt in events
            if (dt := event_start_date(evt)) is not None and dt.date() < self._view_date
        ]
        if not event_dates:
            return None
        return max(event_dates)

    def _find_next_event_date(self) -> date | None:
        now_local = datetime.now().astimezone()
        local_tz = now_local.tzinfo
        day_end = datetime.combine(self._view_date, datetime.min.time(), tzinfo=local_tz) + timedelta(days=1)
        search_start = day_end.astimezone(timezone.utc)
        search_end = (day_end + timedelta(days=365)).astimezone(timezone.utc)
        events = self._client.get_events(search_start, search_end)
        event_dates = [
            dt.date()
            for evt in events
            if (dt := event_start_date(evt)) is not None and dt.date() > self._view_date
        ]
        if not event_dates:
            return None
        return min(event_dates)

    def _reposition(self):
        screen = QApplication.primaryScreen()
        avail  = screen.availableGeometry()
        x = avail.right() - self.width() - 4
        y = avail.bottom() - self.height() - 4
        self.move(x, y)

    def _apply_section_heights(self):
        content_h = self._container.height()
        reserved = self._header.sizeHint().height() + self._footer.sizeHint().height()
        available = max(0, content_h - reserved)
        third = max(1, available // 3)

        self._scroll.setFixedHeight(third)
        self._mail_section.setFixedHeight(third)
        self._alarms_section.setFixedHeight(max(1, available - (2 * third)))

    def _start_populate_async(self):
        self._fetch_request_id += 1
        req_id = self._fetch_request_id
        self._stop_fetch_thread()
        # Immediate visual feedback while worker loads.
        self._populate({"ready": False, "day_events": [], "urgent_events": []})
        worker = _PopupFetchWorker(self._client, self._view_date)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        self._fetch_worker = worker

        def _on_finished(payload):
            thread.quit()
            if req_id != self._fetch_request_id:
                return
            self._populate(payload)
            self._reposition()

        worker.finished.connect(_on_finished)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_fetch_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._fetch_thread = thread
        thread.start()

    def _stop_fetch_thread(self):
        thread = self._fetch_thread
        if thread is None:
            return
        try:
            running = thread.isRunning()
        except RuntimeError:
            self._fetch_thread = None
            self._fetch_worker = None
            return
        if running:
            thread.quit()
            thread.wait(150)
        self._fetch_thread = None
        self._fetch_worker = None

    def _on_fetch_thread_finished(self):
        self._fetch_thread = None
        self._fetch_worker = None

    def _update_mail_section(self, messages: list):
        from settings import get_mail_awareness_enabled
        if not get_mail_awareness_enabled():
            self._mail_section.setVisible(False)
            return

        # Rebuild the row list
        while self._mail_list_layout.count() > 1:
            item = self._mail_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._mail_rows = []

        if not messages:
            self._mail_section.setVisible(True)
            self._mail_count_lbl.setText("")
            empty = QLabel("No unread messages")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setFixedHeight(EmailRow.ROW_HEIGHT)
            empty.setStyleSheet(
                f"color: {c('muted')}; font-size: 11px; font-style: italic; background: transparent;"
            )
            self._mail_list_layout.insertWidget(0, empty)
            self._apply_mail_section_theme()
            return

        noun = "message" if len(messages) == 1 else "messages"
        self._mail_count_lbl.setText(f"{len(messages)} {noun}")

        for i, msg in enumerate(messages):
            row = EmailRow(msg, self._mail_list)
            row.clicked.connect(self._on_mail_row_clicked)
            self._mail_list_layout.insertWidget(i, row)
            self._mail_rows.append(row)

        self._mail_section.setVisible(True)
        self._apply_mail_section_theme()

    def _on_mail_row_clicked(self, message: dict):
        self.hide()
        from dialog_email_reader import EmailReaderDialog
        if self._gmail is None:
            return
        dlg = EmailReaderDialog(message, self._gmail)
        dlg.exec()

    def _apply_mail_section_theme(self):
        self._mail_sep.setStyleSheet(f"background: {c('border')};")
        self._mail_section.setStyleSheet(
            f"QWidget#popupMailSection {{ background: {c('bg')}; }}"
        )
        self._mail_hdr_lbl.setStyleSheet(
            f"color: {c('accent')}; font-size: 10px; font-weight: 600; background: transparent;"
        )
        self._mail_count_lbl.setStyleSheet(
            f"color: {c('dim')}; font-size: 10px; background: transparent;"
        )
        self._mail_scroll.setStyleSheet(f"""
            QScrollArea {{ background: {c('bg')}; border: none; }}
            QScrollBar:vertical {{ width: 4px; background: transparent; }}
            QScrollBar::handle:vertical {{
                background: {c('scroll_handle')}; border-radius: 2px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        self._mail_list.setStyleSheet(f"background: {c('bg')};")
        for row in self._mail_rows:
            row.apply_theme()

    def _apply_alarm_section_theme(self):
        self._alarms_sep.setStyleSheet(f"background: {c('border')};")
        self._alarms_section.setStyleSheet(
            f"QWidget#popupAlarmsSection {{ background: {c('bg')}; }}"
        )
        # Match unread mail heading color/style.
        self._alarms_hdr_lbl.setStyleSheet(
            f"color: {c('accent')}; font-size: 10px; font-weight: 600; background: transparent;"
        )
        self._alarms_count_lbl.setStyleSheet(
            f"color: {c('dim')}; font-size: 10px; background: transparent;"
        )
        self._alarms_list.setStyleSheet(f"background: {c('bg')};")

    def apply_theme(self):
        shadow = self._container.graphicsEffect()
        if shadow is not None:
            shadow.setColor(QColor(c("popup_shadow")))
        self._container.setStyleSheet(f"""
            QWidget#popup_container {{
                background: {c("bg")};
                border-radius: 12px;
                border: 1px solid {c("border")};
            }}
        """)
        self._header.setStyleSheet(f"background: transparent; border-bottom: 1px solid {c('border')};")
        self._footer.setStyleSheet(f"background: transparent; border-top: 1px solid {c('border')};")
        self._date_lbl.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {c('accent')}; background: transparent;"
        )
        self._refresh_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; color: {c('dim')}; font-size: 16px; }}
            QPushButton:hover {{ color: {c('accent')}; }}
        """)
        nav_btn_style = f"""
            QPushButton {{
                background: {c("agenda_btn_bg")};
                border: 1px solid {c("agenda_btn_border")};
                border-radius: 7px;
                color: {c("accent")};
                font-size: 12px;
                font-weight: 500;
                padding: 8px 10px;
            }}
            QPushButton:hover {{
                background: {c("agenda_btn_bg_hover")};
                border-color: {c("agenda_btn_border_hover")};
            }}
        """
        self._prev_event_btn.setStyleSheet(nav_btn_style)
        self._today_btn.setStyleSheet(nav_btn_style)
        self._next_event_btn.setStyleSheet(nav_btn_style)
        self._scroll.setStyleSheet(f"""
            QScrollArea {{ background: {c("bg")}; border: none; }}
            QScrollBar:vertical {{ width: 4px; background: transparent; }}
            QScrollBar::handle:vertical {{
                background: {c("scroll_handle")}; border-radius: 2px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        self._body.setStyleSheet(f"background: {c('bg')};")
        self._apply_mail_section_theme()
        self._apply_alarm_section_theme()
