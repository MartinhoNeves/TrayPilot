"""
settings.py — persistent user settings for TrayPilot.

Backed by Paths.settings_json() with safe defaults and corruption handling.
"""
from __future__ import annotations

import json
from typing import Any

from paths import Paths

DEFAULT_SETTINGS: dict[str, Any] = {
    "theme_mode": "dark",
    "window_size": [780, 520],
    "always_on_top": False,
    "alarm_sound_default": "alarm_event.wav",
    "default_snooze_minutes": 10,
    "mail_awareness_enabled": True,
    "mail_poll_interval_minutes": 5,
    "notify_balloon_new_mail": True,
    "notify_balloon_alarm": True,
}


def _sanitize(data: dict[str, Any]) -> dict[str, Any]:
    merged = dict(DEFAULT_SETTINGS)
    merged.update(data)
    merged["theme_mode"] = "light" if merged.get("theme_mode") == "light" else "dark"
    size = merged.get("window_size")
    if (
        not isinstance(size, list)
        or len(size) != 2
        or not isinstance(size[0], int)
        or not isinstance(size[1], int)
    ):
        merged["window_size"] = list(DEFAULT_SETTINGS["window_size"])
    else:
        w = max(600, size[0])
        h = max(420, size[1])
        merged["window_size"] = [w, h]
    merged["always_on_top"] = bool(merged.get("always_on_top", False))
    sound = str(merged.get("alarm_sound_default") or "alarm_event.wav")
    merged["alarm_sound_default"] = sound
    merged.pop("trust_notice_ack", None)  # legacy key removed (was trust notice)
    merged["mail_awareness_enabled"] = bool(merged.get("mail_awareness_enabled", True))
    interval = merged.get("mail_poll_interval_minutes", 5)
    try:
        interval = max(1, int(interval))
    except (TypeError, ValueError):
        interval = 5
    merged["mail_poll_interval_minutes"] = interval
    snooze = merged.get("default_snooze_minutes", 10)
    try:
        snooze = int(snooze)
    except (TypeError, ValueError):
        snooze = 10
    if snooze not in (5, 10, 15, 30):
        snooze = 10
    merged["default_snooze_minutes"] = snooze
    merged["notify_balloon_new_mail"] = bool(merged.get("notify_balloon_new_mail", True))
    merged["notify_balloon_alarm"] = bool(merged.get("notify_balloon_alarm", True))
    return merged


def load_settings() -> dict[str, Any]:
    path = Paths.settings_json()
    if not path.exists():
        defaults = dict(DEFAULT_SETTINGS)
        save_settings(defaults)
        return defaults

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("settings payload is not an object")
        sanitized = _sanitize(raw)
        if sanitized != raw:
            save_settings(sanitized)
        return sanitized
    except Exception:
        defaults = dict(DEFAULT_SETTINGS)
        save_settings(defaults)
        return defaults


def save_settings(settings: dict[str, Any]) -> dict[str, Any]:
    sanitized = _sanitize(settings)
    Paths.settings_json().write_text(
        json.dumps(sanitized, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    return sanitized


def get_theme_mode() -> str:
    return str(load_settings().get("theme_mode", "dark"))


def set_theme_mode(theme_mode: str) -> None:
    current = load_settings()
    current["theme_mode"] = "light" if theme_mode == "light" else "dark"
    save_settings(current)


def get_window_size() -> tuple[int, int]:
    s = load_settings().get("window_size", [780, 520])
    return int(s[0]), int(s[1])


def set_window_size(width: int, height: int) -> None:
    current = load_settings()
    current["window_size"] = [int(width), int(height)]
    save_settings(current)


def get_always_on_top() -> bool:
    return bool(load_settings().get("always_on_top", False))


def set_always_on_top(value: bool) -> None:
    current = load_settings()
    current["always_on_top"] = bool(value)
    save_settings(current)


def get_alarm_sound_default() -> str:
    return str(load_settings().get("alarm_sound_default", "alarm_event.wav"))


def set_alarm_sound_default(sound_name: str) -> None:
    current = load_settings()
    current["alarm_sound_default"] = str(sound_name or "alarm_event.wav")
    save_settings(current)


def get_mail_awareness_enabled() -> bool:
    return bool(load_settings().get("mail_awareness_enabled", True))


def set_mail_awareness_enabled(value: bool) -> None:
    current = load_settings()
    current["mail_awareness_enabled"] = bool(value)
    save_settings(current)


def get_mail_poll_interval_minutes() -> int:
    raw = load_settings().get("mail_poll_interval_minutes", 5)
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 5


def set_mail_poll_interval_minutes(minutes: int) -> None:
    current = load_settings()
    try:
        current["mail_poll_interval_minutes"] = max(1, int(minutes))
    except (TypeError, ValueError):
        current["mail_poll_interval_minutes"] = 5
    save_settings(current)


def get_default_snooze_minutes() -> int:
    raw = load_settings().get("default_snooze_minutes", 10)
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return 10
    return v if v in (5, 10, 15, 30) else 10


def set_default_snooze_minutes(minutes: int) -> None:
    current = load_settings()
    try:
        m = int(minutes)
    except (TypeError, ValueError):
        m = 10
    current["default_snooze_minutes"] = m if m in (5, 10, 15, 30) else 10
    save_settings(current)


def get_notify_balloon_new_mail() -> bool:
    return bool(load_settings().get("notify_balloon_new_mail", True))


def set_notify_balloon_new_mail(value: bool) -> None:
    current = load_settings()
    current["notify_balloon_new_mail"] = bool(value)
    save_settings(current)


def get_notify_balloon_alarm() -> bool:
    return bool(load_settings().get("notify_balloon_alarm", True))


def set_notify_balloon_alarm(value: bool) -> None:
    current = load_settings()
    current["notify_balloon_alarm"] = bool(value)
    save_settings(current)

