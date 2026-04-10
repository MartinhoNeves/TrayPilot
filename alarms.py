"""
alarms.py — Alarm domain model + persistence helpers.

UI-independent. Stores alarm definitions in Paths.alarms_json().
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from dataclasses import dataclass
from typing import Any

from paths import Paths

RECURRENCE_NONE = "none"
RECURRENCE_DAILY = "daily"
RECURRENCE_WEEKLY = "weekly"
RECURRENCE_MONTHLY = "monthly"
RECURRENCE_YEARLY = "yearly"
VALID_RECURRENCE = {
    RECURRENCE_NONE,
    RECURRENCE_DAILY,
    RECURRENCE_WEEKLY,
    RECURRENCE_MONTHLY,
    RECURRENCE_YEARLY,
}

SOUND_ALARM = "alarm_event.wav"
SOUND_CALENDAR = "calendar_event.wav"
SOUND_EMAIL = "email_event.wav"
SOUND_NONE = ""
VALID_SOUNDS = {SOUND_ALARM, SOUND_CALENDAR, SOUND_EMAIL, SOUND_NONE}


@dataclass
class Alarm:
    id: str
    title: str
    enabled: bool
    next_fire_iso: str
    recurrence: str = RECURRENCE_NONE
    sound: str = SOUND_NONE
    linked_event_id: str = ""
    linked_offset_minutes: int = 0
    created_at_iso: str = ""
    updated_at_iso: str = ""

    @property
    def next_fire(self) -> dt.datetime:
        return parse_iso(self.next_fire_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "enabled": self.enabled,
            "next_fire_iso": self.next_fire_iso,
            "recurrence": self.recurrence,
            "sound": self.sound,
            "linked_event_id": self.linked_event_id,
            "linked_offset_minutes": int(self.linked_offset_minutes),
            "created_at_iso": self.created_at_iso,
            "updated_at_iso": self.updated_at_iso,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Alarm":
        now_iso = now_local().isoformat()
        alarm_id = str(payload.get("id") or uuid.uuid4().hex)
        title = str(payload.get("title") or "Alarm").strip() or "Alarm"
        enabled = bool(payload.get("enabled", True))

        next_fire_iso_raw = payload.get("next_fire_iso")
        if isinstance(next_fire_iso_raw, str):
            try:
                next_fire_iso = parse_iso(next_fire_iso_raw).isoformat()
            except Exception:
                next_fire_iso = now_local().isoformat()
        else:
            next_fire_iso = now_local().isoformat()

        recurrence = str(payload.get("recurrence") or RECURRENCE_NONE)
        if recurrence not in VALID_RECURRENCE:
            recurrence = RECURRENCE_NONE

        sound = str(payload.get("sound") or SOUND_NONE)
        if sound not in VALID_SOUNDS:
            sound = SOUND_NONE

        linked_event_id = str(payload.get("linked_event_id") or "")
        linked_offset_minutes = int(payload.get("linked_offset_minutes") or 0)

        created_at_iso = str(payload.get("created_at_iso") or now_iso)
        updated_at_iso = str(payload.get("updated_at_iso") or now_iso)
        try:
            created_at_iso = parse_iso(created_at_iso).isoformat()
        except Exception:
            created_at_iso = now_iso
        try:
            updated_at_iso = parse_iso(updated_at_iso).isoformat()
        except Exception:
            updated_at_iso = now_iso

        return cls(
            id=alarm_id,
            title=title,
            enabled=enabled,
            next_fire_iso=next_fire_iso,
            recurrence=recurrence,
            sound=sound,
            linked_event_id=linked_event_id,
            linked_offset_minutes=linked_offset_minutes,
            created_at_iso=created_at_iso,
            updated_at_iso=updated_at_iso,
        )


def now_local() -> dt.datetime:
    return dt.datetime.now().astimezone()


def parse_iso(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=now_local().tzinfo)
    return parsed


def _load_raw() -> list[dict[str, Any]]:
    path = Paths.alarms_json()
    if not path.exists():
        save_alarms([])
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return [r for r in raw if isinstance(r, dict)]
        return []
    except Exception:
        save_alarms([])
        return []


def load_alarms() -> list[Alarm]:
    alarms = [Alarm.from_dict(item) for item in _load_raw()]
    alarms.sort(key=lambda a: a.next_fire)
    return alarms


def save_alarms(alarms: list[Alarm]) -> None:
    payload = [a.to_dict() if isinstance(a, Alarm) else Alarm.from_dict(a).to_dict() for a in alarms]
    Paths.alarms_json().write_text(
        json.dumps(payload, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )


def list_alarms() -> list[Alarm]:
    return load_alarms()


def upsert_alarm(alarm: Alarm) -> Alarm:
    now_iso = now_local().isoformat()
    alarms = load_alarms()
    existing = next((a for a in alarms if a.id == alarm.id), None)
    if existing is None:
        alarm.created_at_iso = alarm.created_at_iso or now_iso
    else:
        alarm.created_at_iso = existing.created_at_iso
    alarm.updated_at_iso = now_iso

    next_alarms: list[Alarm] = [a for a in alarms if a.id != alarm.id]
    next_alarms.append(alarm)
    next_alarms.sort(key=lambda a: a.next_fire)
    save_alarms(next_alarms)
    return alarm


def delete_alarm(alarm_id: str) -> bool:
    alarms = load_alarms()
    kept = [a for a in alarms if a.id != alarm_id]
    if len(kept) == len(alarms):
        return False
    save_alarms(kept)
    return True


def get_alarm(alarm_id: str) -> Alarm | None:
    return next((a for a in load_alarms() if a.id == alarm_id), None)


def create_alarm(
    *,
    title: str,
    next_fire: dt.datetime,
    recurrence: str = RECURRENCE_NONE,
    sound: str = SOUND_NONE,
    linked_event_id: str = "",
    linked_offset_minutes: int = 0,
) -> Alarm:
    recurrence = recurrence if recurrence in VALID_RECURRENCE else RECURRENCE_NONE
    sound = sound if sound in VALID_SOUNDS else SOUND_NONE
    alarm = Alarm(
        id=uuid.uuid4().hex,
        title=title.strip() or "Alarm",
        enabled=True,
        next_fire_iso=next_fire.isoformat(),
        recurrence=recurrence,
        sound=sound,
        linked_event_id=linked_event_id,
        linked_offset_minutes=int(linked_offset_minutes),
    )
    return upsert_alarm(alarm)


def snooze_alarm(alarm_id: str, minutes: int) -> Alarm | None:
    alarm = get_alarm(alarm_id)
    if alarm is None:
        return None
    minutes = max(1, int(minutes))
    alarm.next_fire_iso = (now_local() + dt.timedelta(minutes=minutes)).isoformat()
    alarm.enabled = True
    return upsert_alarm(alarm)


def dismiss_alarm(alarm_id: str) -> Alarm | None:
    alarm = get_alarm(alarm_id)
    if alarm is None:
        return None
    if alarm.recurrence == RECURRENCE_NONE:
        alarm.enabled = False
    else:
        alarm.next_fire_iso = advance_fire_time(alarm.next_fire, alarm.recurrence).isoformat()
        alarm.enabled = True
    return upsert_alarm(alarm)


def advance_fire_time(current: dt.datetime, recurrence: str) -> dt.datetime:
    if recurrence == RECURRENCE_DAILY:
        return current + dt.timedelta(days=1)
    if recurrence == RECURRENCE_WEEKLY:
        return current + dt.timedelta(days=7)
    if recurrence == RECURRENCE_MONTHLY:
        month = 1 if current.month == 12 else current.month + 1
        year = current.year + (1 if current.month == 12 else 0)
        day = min(current.day, _days_in_month(year, month))
        return current.replace(year=year, month=month, day=day)
    if recurrence == RECURRENCE_YEARLY:
        year = current.year + 1
        day = min(current.day, _days_in_month(year, current.month))
        return current.replace(year=year, day=day)
    return current


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    first = dt.date(year, month, 1)
    nxt = dt.date(year if month < 12 else year + 1, 1 if month == 12 else month + 1, 1)
    return (nxt - first).days


def recurrence_label(key: str) -> str:
    labels = {
        RECURRENCE_NONE: "Once",
        RECURRENCE_DAILY: "Daily",
        RECURRENCE_WEEKLY: "Weekly",
        RECURRENCE_MONTHLY: "Monthly",
        RECURRENCE_YEARLY: "Yearly",
    }
    return labels.get(key, "Once")


def recalculate_linked_alarms(alarms: list[Alarm], events: list[dict]) -> list[Alarm]:
    """
    Recompute next_fire for calendar-linked alarms based on current event start times.
    """
    by_id: dict[str, dt.datetime] = {}
    for evt in events:
        event_id = str(evt.get("id") or "")
        if not event_id:
            continue
        start = evt.get("start") or {}
        if "dateTime" in start:
            try:
                by_id[event_id] = parse_iso(str(start["dateTime"]))
            except Exception:
                continue
    changed = False
    updated: list[Alarm] = []
    for alarm in alarms:
        if not alarm.linked_event_id:
            updated.append(alarm)
            continue
        start_dt = by_id.get(alarm.linked_event_id)
        if start_dt is None:
            updated.append(alarm)
            continue
        target = start_dt - dt.timedelta(minutes=int(alarm.linked_offset_minutes))
        if alarm.next_fire_iso != target.isoformat():
            alarm.next_fire_iso = target.isoformat()
            alarm.updated_at_iso = now_local().isoformat()
            changed = True
        updated.append(alarm)
    if changed:
        save_alarms(updated)
    return updated
