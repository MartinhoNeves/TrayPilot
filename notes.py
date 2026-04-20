"""
notes.py — Note domain model + persistence (notes.json).

UI-independent. Optional reminders are backed by hidden `Alarm` rows (`note_reminder`).
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from alarms import (
    SOUND_ALARM,
    VALID_SOUNDS,
    create_alarm,
    delete_alarm,
    get_alarm,
    now_local,
    parse_iso,
    upsert_alarm,
)
from paths import Paths


def _normalize_hex_color(value: str, fallback: str = "#f5f5f5") -> str:
    s = str(value or "").strip()
    if len(s) == 7 and s.startswith("#"):
        return s
    return fallback


_NOTE_IMAGE_EXT = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"})
_MAX_NOTE_IMAGES = 16
_MAX_NOTE_IMAGE_BYTES = 12 * 1024 * 1024
# Public alias for UI (clipboard, dialogs).
MAX_IMAGES_PER_NOTE = _MAX_NOTE_IMAGES


def _sanitize_image_files(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for x in raw:
        if not isinstance(x, str) or not x:
            continue
        base = Path(x).name
        if base != x or "/" in x or "\\" in x or ".." in x:
            continue
        if base not in out:
            out.append(base)
        if len(out) >= _MAX_NOTE_IMAGES:
            break
    return out


def _clamp_card_size(w: float, h: float) -> tuple[float, float]:
    # Min width fits footer (colour + Save + Delete) and reminder date/time row.
    w = max(320.0, min(720.0, float(w)))
    h = max(230.0, min(900.0, float(h)))
    return w, h


@dataclass
class Note:
    id: str
    title: str = ""
    body: str = ""
    expanded: bool = True
    # Swatch for the whole card background (see Notes UI); JSON key kept for compatibility.
    title_color_hex: str = "#33b679"
    card_width: float = 340.0
    card_height: float = 300.0
    canvas_x: float = 48.0
    canvas_y: float = 48.0
    reminder_at_iso: str | None = None
    sound: str = SOUND_ALARM
    reminder_alarm_id: str = ""
    created_at_iso: str = ""
    updated_at_iso: str = ""
    # Filenames only, stored under Paths.note_attachments_dir(id).
    image_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "expanded": bool(self.expanded),
            "title_color_hex": _normalize_hex_color(self.title_color_hex),
            "card_width": float(self.card_width),
            "card_height": float(self.card_height),
            "canvas_x": float(self.canvas_x),
            "canvas_y": float(self.canvas_y),
            "reminder_at_iso": self.reminder_at_iso,
            "sound": self.sound,
            "reminder_alarm_id": self.reminder_alarm_id,
            "created_at_iso": self.created_at_iso,
            "updated_at_iso": self.updated_at_iso,
            "image_files": list(self.image_files),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Note":
        now_iso = now_local().isoformat()
        nid = str(payload.get("id") or uuid.uuid4().hex)
        raw_rem = payload.get("reminder_at_iso")
        reminder_at: str | None
        if raw_rem is None or raw_rem == "":
            reminder_at = None
        else:
            reminder_at = str(raw_rem)
        snd = str(payload.get("sound") or SOUND_ALARM)
        if snd not in VALID_SOUNDS:
            snd = SOUND_ALARM
        if "canvas_x" not in payload or "canvas_y" not in payload:
            h = hash(nid) % 100_000
            cx = 48.0 + (h % 5) * 284.0
            cy = 48.0 + ((h // 5) % 4) * 200.0
        else:
            try:
                cx = float(payload.get("canvas_x", 48))
            except (TypeError, ValueError):
                cx = 48.0
            try:
                cy = float(payload.get("canvas_y", 48))
            except (TypeError, ValueError):
                cy = 48.0
        tcol = _normalize_hex_color(str(payload.get("title_color_hex") or "#33b679"))
        try:
            cw = float(payload.get("card_width", 340))
        except (TypeError, ValueError):
            cw = 340.0
        try:
            ch = float(payload.get("card_height", 300))
        except (TypeError, ValueError):
            ch = 300.0
        cw, ch = _clamp_card_size(cw, ch)
        imgs = _sanitize_image_files(
            payload.get("image_files", payload.get("images"))
        )
        return cls(
            id=nid,
            title=str(payload.get("title") or ""),
            body=str(payload.get("body") or ""),
            expanded=bool(payload.get("expanded", True)),
            title_color_hex=tcol,
            card_width=cw,
            card_height=ch,
            canvas_x=cx,
            canvas_y=cy,
            reminder_at_iso=reminder_at,
            sound=snd,
            reminder_alarm_id=str(payload.get("reminder_alarm_id") or ""),
            created_at_iso=str(payload.get("created_at_iso") or now_iso),
            updated_at_iso=str(payload.get("updated_at_iso") or now_iso),
            image_files=imgs,
        )


def _load_raw() -> list[dict[str, Any]]:
    path = Paths.notes_json()
    if not path.exists():
        save_notes([])
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return [r for r in raw if isinstance(r, dict)]
        return []
    except Exception:
        save_notes([])
        return []


def load_notes() -> list[Note]:
    return [Note.from_dict(item) for item in _load_raw()]


def save_notes(notes: list[Note]) -> None:
    payload = [n.to_dict() if isinstance(n, Note) else Note.from_dict(n).to_dict() for n in notes]
    Paths.notes_json().write_text(
        json.dumps(payload, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )


def get_note(note_id: str) -> Note | None:
    nid = str(note_id or "")
    if not nid:
        return None
    return next((n for n in load_notes() if n.id == nid), None)


def replace_note(updated: Note) -> None:
    now_iso = now_local().isoformat()
    updated.updated_at_iso = now_iso
    notes = load_notes()
    if not any(n.id == updated.id for n in notes):
        updated.created_at_iso = updated.created_at_iso or now_iso
        notes.append(updated)
    else:
        out: list[Note] = []
        for n in notes:
            if n.id == updated.id:
                updated.created_at_iso = n.created_at_iso or updated.created_at_iso
                out.append(updated)
            else:
                out.append(n)
        notes = out

    def _sort_key(n: Note) -> dt.datetime:
        try:
            return parse_iso(n.updated_at_iso)
        except Exception:
            return now_local()

    notes.sort(key=_sort_key, reverse=True)
    save_notes(notes)


def delete_note(note_id: str) -> bool:
    nid = str(note_id or "")
    if not nid:
        return False
    note = get_note(nid)
    if note is None:
        return False
    if note.reminder_alarm_id:
        delete_alarm(note.reminder_alarm_id)
    att_dir = Paths.data_dir() / "note_attachments" / nid
    if att_dir.is_dir():
        shutil.rmtree(att_dir, ignore_errors=True)
    notes = [n for n in load_notes() if n.id != nid]
    save_notes(notes)
    return True


def new_note(*, canvas_x: float = 48.0, canvas_y: float = 48.0) -> Note:
    now_iso = now_local().isoformat()
    return Note(
        id=uuid.uuid4().hex,
        title="",
        body="",
        expanded=True,
        title_color_hex="#33b679",
        card_width=340.0,
        card_height=300.0,
        canvas_x=float(canvas_x),
        canvas_y=float(canvas_y),
        reminder_at_iso=None,
        sound=SOUND_ALARM,
        reminder_alarm_id="",
        created_at_iso=now_iso,
        updated_at_iso=now_iso,
    )


def patch_note_canvas_position(note_id: str, x: float, y: float) -> None:
    n = get_note(note_id)
    if n is None:
        return
    n.canvas_x = float(x)
    n.canvas_y = float(y)
    replace_note(n)


def patch_note_expanded(note_id: str, expanded: bool) -> None:
    n = get_note(note_id)
    if n is None:
        return
    n.expanded = bool(expanded)
    replace_note(n)


def patch_note_card_size(note_id: str, width: float, height: float) -> None:
    n = get_note(note_id)
    if n is None:
        return
    cw, ch = _clamp_card_size(width, height)
    n.card_width = cw
    n.card_height = ch
    replace_note(n)


def sync_note_reminder(note: Note) -> None:
    """
    Rebuild the hidden alarm row from `note.reminder_at_iso` / sound / title.
    Call after changing reminder fields or title/sound while a reminder exists.
    """
    if note.reminder_alarm_id:
        delete_alarm(note.reminder_alarm_id)
        note.reminder_alarm_id = ""

    if not note.reminder_at_iso:
        replace_note(note)
        return

    try:
        when = parse_iso(note.reminder_at_iso)
    except Exception:
        note.reminder_at_iso = None
        replace_note(note)
        return

    if when <= now_local():
        note.reminder_at_iso = None
        replace_note(note)
        return

    sound = note.sound if note.sound in VALID_SOUNDS else SOUND_ALARM
    alarm = create_alarm(
        title=(note.title or "Note").strip() or "Note",
        next_fire=when,
        sound=sound,
        note_reminder=True,
        linked_note_id=note.id,
    )
    note.reminder_alarm_id = alarm.id
    replace_note(note)


def clear_note_reminder_schedule(note_id: str) -> None:
    """Remove hidden alarm and reminder fields (e.g. user dismissed the reminder dialog)."""
    note = get_note(note_id)
    if note is None:
        return
    if note.reminder_alarm_id:
        delete_alarm(note.reminder_alarm_id)
    note.reminder_alarm_id = ""
    note.reminder_at_iso = None
    replace_note(note)


def patch_note_reminder_after_snooze(note_id: str, alarm_id: str) -> None:
    """After snooze, align stored reminder time with the alarm's new next_fire."""
    alarm = get_alarm(alarm_id)
    note = get_note(note_id)
    if alarm is None or note is None:
        return
    note.reminder_at_iso = alarm.next_fire_iso
    note.reminder_alarm_id = alarm.id
    replace_note(note)


def refresh_note_reminder_title(note: Note) -> None:
    """If a reminder alarm exists, keep its title in sync with the note (for dialog display)."""
    if not note.reminder_alarm_id:
        return
    alarm = get_alarm(note.reminder_alarm_id)
    if alarm is None:
        note.reminder_alarm_id = ""
        replace_note(note)
        return
    t = (note.title or "Note").strip() or "Note"
    if alarm.title != t:
        alarm.title = t
        upsert_alarm(alarm)


def add_image_to_note(note_id: str, src_path: Path) -> str | None:
    """
    Copy an image file into note attachments and append to note.image_files.
    Returns the stored filename, or None if invalid / over limit / note missing.
    """
    nid = str(note_id or "")
    if not nid:
        return None
    n = get_note(nid)
    if n is None:
        return None
    if len(n.image_files) >= _MAX_NOTE_IMAGES:
        return None
    src = Path(src_path)
    if not src.is_file():
        return None
    ext = src.suffix.lower()
    if ext not in _NOTE_IMAGE_EXT:
        return None
    try:
        if src.stat().st_size > _MAX_NOTE_IMAGE_BYTES:
            return None
    except OSError:
        return None
    dest_dir = Paths.note_attachments_dir(nid)
    name = f"{uuid.uuid4().hex}{ext}"
    try:
        shutil.copy2(src, dest_dir / name)
    except OSError:
        return None
    n.image_files = list(n.image_files) + [name]
    replace_note(n)
    return name


def register_note_attachment_file(note_id: str, filename: str) -> bool:
    """
    Append an image filename after the file has been written under
    Paths.note_attachments_dir(note_id). Validates type, size, and count.
    """
    nid = str(note_id or "")
    fn = str(filename or "").strip()
    if not nid or not fn:
        return False
    n = get_note(nid)
    if n is None:
        return False
    if len(n.image_files) >= _MAX_NOTE_IMAGES:
        return False
    if fn in n.image_files:
        return True
    p = Paths.note_attachments_dir(nid) / fn
    if not p.is_file():
        return False
    ext = p.suffix.lower()
    if ext not in _NOTE_IMAGE_EXT:
        try:
            p.unlink()
        except OSError:
            pass
        return False
    try:
        if p.stat().st_size > _MAX_NOTE_IMAGE_BYTES:
            try:
                p.unlink()
            except OSError:
                pass
            return False
    except OSError:
        return False
    n.image_files = list(n.image_files) + [fn]
    replace_note(n)
    return True


def remove_note_image(note_id: str, filename: str) -> None:
    """Delete attachment file and remove its name from the note."""
    nid = str(note_id or "")
    fn = str(filename or "").strip()
    if not nid or not fn:
        return
    n = get_note(nid)
    if n is None or fn not in n.image_files:
        return
    p = Paths.note_attachments_dir(nid) / fn
    if p.is_file():
        try:
            p.unlink()
        except OSError:
            pass
    n.image_files = [x for x in n.image_files if x != fn]
    replace_note(n)
