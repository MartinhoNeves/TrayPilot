"""
alarm_scheduler.py — alarm timing engine.

UI-independent scheduler that polls alarms every 30s and emits alarm_fired.
"""
from __future__ import annotations

import datetime as dt

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from alarms import Alarm, dismiss_alarm, list_alarms, parse_iso, snooze_alarm


class AlarmScheduler(QObject):
    alarm_fired = pyqtSignal(object)  # Alarm
    alarms_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fired_ids: set[str] = set()
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(30_000)
        self._poll_timer.timeout.connect(self._poll_due_alarms)
        self._precise_timer = QTimer(self)
        self._precise_timer.setSingleShot(True)
        self._precise_timer.timeout.connect(self._poll_due_alarms)

    def start(self) -> None:
        self._poll_due_alarms()
        self._poll_timer.start()
        self._arm_precise_timer()

    def stop(self) -> None:
        self._poll_timer.stop()
        self._precise_timer.stop()

    def refresh(self) -> None:
        self._fired_ids.clear()
        self.alarms_changed.emit()
        self._poll_due_alarms()
        self._arm_precise_timer()

    def dismiss(self, alarm_id: str) -> Alarm | None:
        alarm = dismiss_alarm(alarm_id)
        self._fired_ids.discard(alarm_id)
        self.alarms_changed.emit()
        self._arm_precise_timer()
        return alarm

    def snooze(self, alarm_id: str, minutes: int) -> Alarm | None:
        alarm = snooze_alarm(alarm_id, minutes)
        self._fired_ids.discard(alarm_id)
        self.alarms_changed.emit()
        self._arm_precise_timer()
        return alarm

    def _poll_due_alarms(self) -> None:
        now = dt.datetime.now().astimezone()
        fired_any = False
        for alarm in list_alarms():
            if not alarm.enabled:
                self._fired_ids.discard(alarm.id)
                continue
            fire_time = parse_iso(alarm.next_fire_iso)
            if fire_time > now:
                self._fired_ids.discard(alarm.id)
                continue
            if alarm.id in self._fired_ids:
                continue
            self._fired_ids.add(alarm.id)
            self.alarm_fired.emit(alarm)
            fired_any = True
        if fired_any:
            self.alarms_changed.emit()
        self._arm_precise_timer()

    def _arm_precise_timer(self) -> None:
        now = dt.datetime.now().astimezone()
        next_due: dt.datetime | None = None
        for alarm in list_alarms():
            if not alarm.enabled:
                continue
            fire_time = parse_iso(alarm.next_fire_iso)
            if fire_time <= now:
                # Already due — trigger processing immediately.
                self._precise_timer.start(0)
                return
            if next_due is None or fire_time < next_due:
                next_due = fire_time
        if next_due is None:
            self._precise_timer.stop()
            return
        delay_ms = int((next_due - now).total_seconds() * 1000)
        delay_ms = max(1, min(delay_ms, 2_147_483_000))
        self._precise_timer.start(delay_ms)
