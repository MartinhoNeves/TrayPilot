"""
widget_calendar.py — CalendarWidget with custom nav bar (month + year comboboxes).

Architecture: CalendarWidget is a QWidget wrapper around an inner QCalendarWidget
whose built-in nav bar is hidden. The wrapper owns a custom nav bar with ◄,
month combobox, year combobox, and ►. This avoids any manipulation of Qt-internal
widgets and gives full styling control.
"""
from __future__ import annotations

import datetime

from PyQt6.QtCore import QDate, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QIcon, QPainter, QTextCharFormat
from PyQt6.QtWidgets import (
    QCalendarWidget, QComboBox, QHBoxLayout, QToolButton, QVBoxLayout, QWidget,
)

from colour_theme import c

_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_YEAR_MIN = 2010
_YEAR_MAX = 2040


# ── Inner calendar (paintCell + dots only) ────────────────────────────────────

class _InnerCalendar(QCalendarWidget):
    """QCalendarWidget with nav bar hidden — used inside CalendarWidget wrapper."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._event_dates:  set[datetime.date] = set()
        self._urgent_dates: set[datetime.date] = set()

        self.setNavigationBarVisible(False)
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        self.setGridVisible(False)

        cell_font = QFont()
        cell_font.setPixelSize(11)
        self.setFont(cell_font)

        self._apply_style()
        self._apply_weekday_colors()

    def set_event_dates(self, event_dates: set[datetime.date], urgent_dates: set[datetime.date]):
        self._event_dates  = event_dates
        self._urgent_dates = urgent_dates
        self.update()

    def apply_theme(self):
        self._apply_weekday_colors()
        self._apply_style()
        self.update()

    def _apply_weekday_colors(self):
        weekday_fmt = QTextCharFormat()
        weekday_fmt.setForeground(QColor(c("calendar_text")))
        for weekday in (
            Qt.DayOfWeek.Monday,
            Qt.DayOfWeek.Tuesday,
            Qt.DayOfWeek.Wednesday,
            Qt.DayOfWeek.Thursday,
            Qt.DayOfWeek.Friday,
        ):
            self.setWeekdayTextFormat(weekday, weekday_fmt)

        # Explicitly override Qt's default weekend red with dim gray.
        weekend_fmt = QTextCharFormat()
        weekend_fmt.setForeground(QColor(c("dim")))
        self.setWeekdayTextFormat(Qt.DayOfWeek.Saturday, weekend_fmt)
        self.setWeekdayTextFormat(Qt.DayOfWeek.Sunday, weekend_fmt)

    def _apply_style(self):
        self.setStyleSheet(f"""
            QCalendarWidget {{
                background: {c("bg")};
            }}
            QCalendarWidget QWidget#qt_calendar_calendarview {{
                background: {c("bg")};
                selection-background-color: transparent;
                selection-color: {c("accent")};
                outline: none;
            }}
            QCalendarWidget QWidget#qt_calendar_calendarview:disabled {{
                color: {c("calendar_other_month")};
            }}
            QCalendarWidget QHeaderView {{
                background: {c("bg")};
            }}
            QCalendarWidget QHeaderView::section {{
                background: {c("bg")};
                color: {c("calendar_text")};
                font-size: 10px;
                font-weight: 600;
                border: none;
                padding: 4px 0;
            }}
        """)

    def paintCell(self, painter: QPainter, rect: QRect, date: QDate):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        today         = QDate.currentDate()
        selected      = self.selectedDate()
        current_month = self.monthShown()

        is_today       = date == today
        is_selected    = date == selected
        is_other_month = date.month() != current_month

        py_date = datetime.date(date.year(), date.month(), date.day())

        if is_selected and not is_today:
            painter.fillRect(rect, QColor(c("calendar_selected_overlay")))
        elif rect.contains(self.mapFromGlobal(QCursor.pos())):
            painter.fillRect(rect, QColor("#334155"))
        else:
            painter.fillRect(rect, QColor(c("bg")))

        cx = rect.center().x()
        circle_size = 26
        circle_rect = QRect(cx - circle_size // 2, rect.top() + 5, circle_size, circle_size)

        if is_today:
            painter.setBrush(QColor(c("accent")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(circle_rect)
            painter.setPen(QColor(c("bg")))
        elif is_other_month:
            painter.setPen(QColor(c("calendar_other_month")))
        elif is_selected:
            painter.setPen(QColor(c("accent")))
        else:
            painter.setPen(QColor(c("calendar_text")))

        painter.drawText(circle_rect, Qt.AlignmentFlag.AlignCenter, str(date.day()))

        if not is_other_month:
            has_urgent = py_date in self._urgent_dates
            has_event  = py_date in self._event_dates
            if has_urgent or has_event:
                dot_y    = rect.top() + 5 + circle_size + 3
                dot_size = 4
                painter.setPen(Qt.PenStyle.NoPen)
                if has_urgent and has_event:
                    painter.setBrush(QColor(c("danger")))
                    painter.drawEllipse(cx - 5, dot_y, dot_size, dot_size)
                    painter.setBrush(QColor(c("accent")))
                    painter.drawEllipse(cx + 2, dot_y, dot_size, dot_size)
                elif has_urgent:
                    painter.setBrush(QColor(c("danger")))
                    painter.drawEllipse(cx - 2, dot_y, dot_size, dot_size)
                else:
                    painter.setBrush(QColor(c("accent")))
                    painter.drawEllipse(cx - 2, dot_y, dot_size, dot_size)

        # Subtle day-cell grid for both themes.
        painter.setPen(QColor(c("calendar_grid")))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect.adjusted(0, 0, -1, -1))

        painter.restore()


# ── Public wrapper ────────────────────────────────────────────────────────────

class CalendarWidget(QWidget):
    """
    QWidget wrapper around _InnerCalendar.
    Exposes the same signals and methods used by window_main.py.
    """

    clicked            = pyqtSignal(QDate)
    currentPageChanged = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._inner = _InnerCalendar(self)
        self._min_page: tuple[int, int] | None = None
        self._max_page: tuple[int, int] | None = None

        # ── Custom nav bar ────────────────────────────────────────────────────
        self._nav = QWidget()
        self._nav.setObjectName("calNavBar")
        nav_layout = QHBoxLayout(self._nav)
        nav_layout.setContentsMargins(6, 0, 6, 0)
        nav_layout.setSpacing(4)

        self._prev_btn = QToolButton()
        self._prev_btn.setObjectName("calNavBtn")
        self._prev_btn.setText("\u25C0")
        self._prev_btn.clicked.connect(self._inner.showPreviousMonth)

        self._month_combo = QComboBox()
        self._month_combo.setObjectName("calMonthCombo")
        for i, name in enumerate(_MONTHS):
            self._month_combo.addItem(name, i + 1)  # userData = month number (1-12)

        self._year_combo = QComboBox()
        self._year_combo.setObjectName("calYearCombo")
        for yr in range(_YEAR_MIN, _YEAR_MAX + 1):
            self._year_combo.addItem(str(yr), yr)

        self._next_btn = QToolButton()
        self._next_btn.setObjectName("calNavBtn")
        self._next_btn.setText("\u25B6")
        self._next_btn.clicked.connect(self._inner.showNextMonth)

        nav_layout.addStretch()
        nav_layout.addWidget(self._prev_btn)
        nav_layout.addWidget(self._month_combo)
        nav_layout.addWidget(self._year_combo)
        nav_layout.addWidget(self._next_btn)
        nav_layout.addStretch()

        # ── Outer layout ──────────────────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._nav)
        layout.addWidget(self._inner)

        # ── Sync combos to current page ───────────────────────────────────────
        self._sync_nav()

        # ── Wire signals ──────────────────────────────────────────────────────
        self._month_combo.currentIndexChanged.connect(self._on_month_combo)
        self._year_combo.currentIndexChanged.connect(self._on_year_combo)
        self._inner.currentPageChanged.connect(self._on_inner_page_changed)
        self._inner.clicked.connect(self.clicked)

        self.apply_theme()

    # ── Sync helpers ──────────────────────────────────────────────────────────

    def _sync_nav(self):
        """Sync combo selections to the current inner page (uses userData lookup)."""
        month = self._inner.monthShown()
        year  = self._inner.yearShown()

        self._month_combo.blockSignals(True)
        idx = self._month_combo.findData(month)
        if idx >= 0:
            self._month_combo.setCurrentIndex(idx)
        self._month_combo.blockSignals(False)

        self._year_combo.blockSignals(True)
        idx = self._year_combo.findData(year)
        if idx >= 0:
            self._year_combo.setCurrentIndex(idx)
        self._year_combo.blockSignals(False)

    def _rebuild_month_combo(self, year: int):
        """Repopulate month combo with only the months valid for this year."""
        if self._min_page is None or self._max_page is None:
            # No bounds set — show all months
            start_m, end_m = 1, 12
        else:
            min_year, min_month = self._min_page
            max_year, max_month = self._max_page
            start_m = min_month if year == min_year else 1
            end_m   = max_month if year == max_year else 12

        self._month_combo.blockSignals(True)
        self._month_combo.clear()
        for m in range(start_m, end_m + 1):
            self._month_combo.addItem(_MONTHS[m - 1], m)
        self._month_combo.blockSignals(False)

    def _on_month_combo(self, index: int):
        month = self._month_combo.itemData(index)
        if month is not None:
            self._inner.setCurrentPage(self._inner.yearShown(), month)

    def _on_year_combo(self, index: int):
        year = self._year_combo.itemData(index)
        if year is None:
            return
        month = self._inner.monthShown()
        # Clamp month to valid range for the newly selected year
        if self._min_page and self._max_page:
            min_year, min_month = self._min_page
            max_year, max_month = self._max_page
            if year == min_year:
                month = max(month, min_month)
            if year == max_year:
                month = min(month, max_month)
        self._inner.setCurrentPage(year, month)

    def _on_inner_page_changed(self, year: int, month: int):
        self._rebuild_month_combo(year)
        self._sync_nav()
        self._update_nav_buttons()
        self.currentPageChanged.emit(year, month)

    # ── Public API (mirrors what window_main.py expects) ──────────────────────

    def yearShown(self) -> int:
        return self._inner.yearShown()

    def monthShown(self) -> int:
        return self._inner.monthShown()

    def selectedDate(self) -> QDate:
        return self._inner.selectedDate()

    def setSelectedDate(self, date: QDate):
        self._inner.setSelectedDate(date)

    def setCurrentPage(self, year: int, month: int):
        self._inner.setCurrentPage(year, month)

    def set_nav_bounds(self, min_year: int, min_month: int, max_year: int, max_month: int):
        """Restrict navigation to the given range and update combos + arrow buttons."""
        self._min_page = (min_year, min_month)
        self._max_page = (max_year, max_month)

        # Rebuild year combo to only list years within the allowed range
        cur_year = self._inner.yearShown()
        self._year_combo.blockSignals(True)
        self._year_combo.clear()
        for yr in range(min_year, max_year + 1):
            self._year_combo.addItem(str(yr), yr)
        self._year_combo.blockSignals(False)

        # Rebuild month combo for the current year, then sync selections
        self._rebuild_month_combo(cur_year)
        self._sync_nav()
        self._update_nav_buttons()

    def _update_nav_buttons(self):
        if self._min_page is None or self._max_page is None:
            return
        page = (self._inner.yearShown(), self._inner.monthShown())
        self._prev_btn.setEnabled(page > self._min_page)
        self._next_btn.setEnabled(page < self._max_page)

    def set_event_dates(self, event_dates: set[datetime.date], urgent_dates: set[datetime.date]):
        self._inner.set_event_dates(event_dates, urgent_dates)

    # ── Theme ─────────────────────────────────────────────────────────────────

    def apply_theme(self):
        self._inner.apply_theme()
        self._apply_nav_style()

    def _apply_nav_style(self):
        combo_style = f"""
            QComboBox {{
                color: {c("calendar_spin_text")};
                background: transparent;
                border: none;
                font-size: 14px;
                font-weight: 600;
                padding: 2px 4px;
                min-width: 62px;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: right center;
                width: 14px;
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background: {c("titlebar")};
                color: {c("text")};
                selection-background-color: {c("accent")};
                selection-color: {c("bg")};
                border: 1px solid {c("border")};
                outline: none;
            }}
        """
        self._month_combo.setStyleSheet(combo_style)
        self._year_combo.setStyleSheet(combo_style)

        self._nav.setStyleSheet(f"""
            QWidget#calNavBar {{
                background: {c("titlebar")};
                border-bottom: 1px solid {c("border")};
                min-height: 40px;
            }}
            QToolButton#calNavBtn {{
                color: {c("calendar_nav_arrow")};
                background: transparent;
                border: none;
                font-size: 18px;
                font-weight: 700;
                padding: 4px 6px;
                border-radius: 5px;
            }}
            QToolButton#calNavBtn:hover {{
                color: {c("accent")};
                background: {c("calendar_tool_hover_bg")};
            }}
        """)
