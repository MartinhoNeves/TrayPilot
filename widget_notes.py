"""
widget_notes.py — Notes tab: freeform canvas of compact note cards (drag, title color, Save).
"""
from __future__ import annotations

import datetime as dt
import uuid
from functools import partial
from pathlib import Path

from PyQt6.QtCore import QEvent, QDateTime, QPoint, QRect, Qt, QTimer
from PyQt6.QtGui import (
    QColor,
    QKeySequence,
    QPalette,
    QPixmap,
    QResizeEvent,
    QShowEvent,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QFileDialog,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from alarm_scheduler import AlarmScheduler
from colour_theme import c
from paths import Paths
from notes import (
    MAX_IMAGES_PER_NOTE,
    Note,
    add_image_to_note,
    delete_note,
    get_note,
    load_notes,
    new_note,
    patch_note_canvas_position,
    patch_note_card_size,
    patch_note_expanded,
    refresh_note_reminder_title,
    register_note_attachment_file,
    remove_note_image,
    replace_note,
    sync_note_reminder,
)

NOTE_DEFAULT_W = 340
NOTE_DEFAULT_H = 300
NOTE_MIN_W = 320
NOTE_MIN_H = 230
CANVAS_MARGIN = 48
CANVAS_MIN_W = 1000
CANVAS_MIN_H = 720

# (label, hex) — full card background presets (includes brand accent)
CARD_COLOR_OPTIONS = [
    ("White", "#f5f5f5"),
    ("Accent", "#e8922a"),
    ("Lavender", "#7986cb"),
    ("Sage", "#33b679"),
    ("Grape", "#8e24aa"),
    ("Flamingo", "#e67c73"),
    ("Banana", "#f6c026"),
    ("Peacock", "#039be5"),
    ("Graphite", "#9e9e9e"),
    ("Tomato", "#ea4335"),
    ("Basil", "#0b8043"),
]


class ImagePreviewDialog(QDialog):
    """Native 1:1 pixel preview (no scaling). Scroll if larger than the viewport. Esc or Close."""

    def __init__(self, parent: QWidget | None, image_path: Path) -> None:
        super().__init__(parent)
        self._full_pix = QPixmap(str(image_path))
        self.setWindowTitle("Image preview")
        self.setModal(True)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint
        )
        self.setObjectName("imagePreviewDialog")
        self.setStyleSheet(
            """
            QDialog#imagePreviewDialog { background-color: #121218; }
            QScrollArea#imagePreviewScroll {
                background-color: #121218;
                border: none;
            }
            """
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("imagePreviewScroll")
        self._scroll.setWidgetResizable(False)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self._label = QLabel()
        self._label.setScaledContents(False)
        self._label.setPixmap(self._full_pix)
        if self._full_pix.isNull():
            self._label.setMinimumSize(64, 64)
        else:
            self._label.setFixedSize(self._full_pix.size())
        self._scroll.setWidget(self._label)
        lay.addWidget(self._scroll, 1)

        hint = QLabel("Esc or the window close button to return")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #a8a8b0; font-size: 12px;")
        lay.addWidget(hint)

        self._apply_viewport_and_fixed_size()

    def _apply_viewport_and_fixed_size(self) -> None:
        """Cap window to the screen; image stays at original resolution inside scroll bars."""
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        footer = 36
        chrome = 8 * 4 + footer + 8
        if self._full_pix.isNull():
            vw, vh = 320, 240
        else:
            vw = min(self._full_pix.width(), max(120, avail.width() - 48))
            vh = min(self._full_pix.height(), max(80, avail.height() - chrome))
        self._scroll.setFixedSize(int(vw), int(vh))
        w = int(vw + 16)
        h = int(vh + footer + 16)
        w = min(w, avail.width() - 16)
        h = min(h, avail.height() - 16)
        self.setFixedSize(max(w, 200), max(h, 120))

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(e)


def _parse_hex_rgb(hex_col: str) -> tuple[int, int, int]:
    hx = str(hex_col or "").strip().lstrip("#")
    if len(hx) != 6:
        return 54, 58, 78
    try:
        return int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
    except ValueError:
        return 54, 58, 78


def _mix_hex(a: str, b: str, t: float) -> str:
    """Linear RGB mix: t=0 → a, t=1 → b."""
    r1, g1, b1 = _parse_hex_rgb(a)
    r2, g2, b2 = _parse_hex_rgb(b)
    t = max(0.0, min(1.0, t))
    r = int(round(r1 + (r2 - r1) * t))
    g = int(round(g1 + (g2 - g1) * t))
    b = int(round(b1 + (b2 - b1) * t))
    return f"#{r:02x}{g:02x}{b:02x}"


def _relative_luminance(hex_col: str) -> float:
    r, g, b = _parse_hex_rgb(hex_col)

    def _lin(ch: float) -> float:
        c = ch / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * _lin(float(r)) + 0.7152 * _lin(float(g)) + 0.0722 * _lin(float(b))


def _card_palette(bg_hex: str) -> dict[str, str]:
    """Text, borders, and inset fields derived from the card colour (coherent tinting)."""
    lum = _relative_luminance(bg_hex)
    # Mid oranges (Accent) stay on the light-text branch; threshold avoids muddy flip-flop.
    light_surface = lum > 0.40
    if light_surface:
        text = "#141418"
        muted = _mix_hex("#4a4a55", bg_hex, 0.2)
    else:
        text = "#f2f2f6"
        muted = _mix_hex("#c8c8d4", bg_hex, 0.2)

    inset = _mix_hex(bg_hex, text, 0.16)
    chrome = _mix_hex(bg_hex, text, 0.32)
    border = _mix_hex(bg_hex, text, 0.24)
    placeholder = _mix_hex(bg_hex, text, 0.42)
    list_bg = _mix_hex(bg_hex, text, 0.08)
    list_sel = _mix_hex("#e8922a", list_bg, 0.45)

    if light_surface:
        save_border = _mix_hex("#7a4a00", bg_hex, 0.55)
        cb_checked = _mix_hex("#b86a12", bg_hex, 0.35)
    else:
        save_border = _mix_hex("#ffe0b2", bg_hex, 0.5)
        cb_checked = _mix_hex("#e8922a", bg_hex, 0.4)

    dt_dim_fg = _mix_hex(text, bg_hex, 0.55)
    dt_dim_bg = _mix_hex(inset, bg_hex, 0.45)
    return {
        "bg": bg_hex,
        "text": text,
        "muted": muted,
        "border": border,
        "inset": inset,
        "chrome": chrome,
        "dt_dim_fg": dt_dim_fg,
        "dt_dim_bg": dt_dim_bg,
        # Same glyph colour on move + resize handles (readable on chrome chip).
        "chrome_fg": text,
        "placeholder": placeholder,
        "save_border": save_border,
        "list_bg": list_bg,
        "list_text": text,
        "list_sel": list_sel,
        "cb_border": _mix_hex(border, text, 0.35),
        "cb_checked": cb_checked,
    }


class NotesCanvas(QWidget):
    """Scrollable surface; children are NoteCard widgets at absolute positions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict[str, "NoteCard"] = {}
        self.setObjectName("notesCanvas")
        self._apply_bg()
        self.resize(CANVAS_MIN_W, CANVAS_MIN_H)

    def clear_registry(self) -> None:
        self._cards.clear()

    def _apply_bg(self):
        self.setStyleSheet(
            f"""
            QWidget#notesCanvas {{
                background: {c("bg")};
                border: 1px dashed {c("border")};
                border-radius: 6px;
            }}
            """
        )

    def register_card(self, card: "NoteCard") -> None:
        self._cards[card.note_id()] = card

    def unregister_card(self, note_id: str) -> None:
        self._cards.pop(note_id, None)

    def resize_to_fit_cards(self) -> None:
        max_r = CANVAS_MIN_W
        max_b = CANVAS_MIN_H
        for card in self._cards.values():
            max_r = max(max_r, card.x() + card.width() + CANVAS_MARGIN)
            max_b = max(max_b, card.y() + card.height() + CANVAS_MARGIN)
        max_r = int(max_r)
        max_b = int(max_b)
        self.setMinimumSize(max_r, max_b)
        # Explicit size is required when the scroll area is not widget-resizable.
        self.resize(max_r, max_b)


class NoteCard(QFrame):
    def __init__(
        self,
        note: Note,
        scheduler: AlarmScheduler,
        canvas: NotesCanvas,
        host: "NotesWidget",
    ):
        super().__init__(canvas)
        self._canvas = canvas
        self._host = host
        self._scheduler = scheduler
        self._note_id = note.id
        self._expanded = note.expanded
        self._drag_active = False
        self._press_global = QPoint()
        self._start_pos = QPoint()
        self._resize_active = False
        self._resize_press = QPoint()
        self._resize_start_geom = QRect()
        self._drag_handle = None
        self._resize_grip = None
        self._card_color_hex = "#33b679"
        self._save_flash_timer = QTimer(self)
        self._save_flash_timer.setSingleShot(True)
        self._save_flash_timer.timeout.connect(self._end_save_flash_theme)

        self.setObjectName("noteCard")
        self._build_ui()
        self._load_from_note(note)
        self._apply_fold_state()
        self.move(int(note.canvas_x), int(note.canvas_y))
        self.apply_theme()
        self._canvas.register_card(self)
        # Children on a canvas without a layout often stay hidden until explicitly shown
        # (e.g. NotesWidget first rebuild runs before the tab is visible).
        self.show()
        self.raise_()
        if self._expanded:
            QTimer.singleShot(0, self._reflow_height)

    def note_id(self) -> str:
        return self._note_id

    def apply_theme(self, *, save_flash: bool = False) -> None:
        if not save_flash:
            self._save_flash_timer.stop()
        bg = self._title_color_hex()
        pal = _card_palette(bg)
        if save_flash:
            frame_bg = _mix_hex(bg, pal["text"], 0.2)
            frame_border = (
                f"2px solid {_mix_hex('#f0c96a', pal['border'], 0.55)}"
            )
        else:
            frame_bg = bg
            frame_border = f"1px solid {pal['border']}"
        self.setStyleSheet(
            f"""
            QFrame#noteCard {{
                background: {frame_bg};
                border: {frame_border};
                border-radius: 8px;
            }}
            QLineEdit#noteCardTitle {{
                background: {pal["inset"]};
                border: 1px solid {pal["border"]};
                border-radius: 4px;
                padding: 5px;
                font-size: 12px;
                font-weight: 600;
                color: {pal["text"]};
            }}
            QPlainTextEdit#noteCardBody {{
                background: {pal["inset"]};
                color: {pal["text"]};
                border: 1px solid {pal["border"]};
                border-radius: 4px;
                padding: 6px;
                font-size: 11px;
            }}
            QToolButton#noteCardFoldBtn {{
                background: transparent;
                color: {pal["text"]};
                border: none;
                font-size: 13px;
                padding: 2px 4px;
            }}
            QLabel#noteDragHandle, QLabel#noteResizeGrip {{
                background: {pal["chrome"]};
                color: {pal["chrome_fg"]};
                font-size: 12px;
                font-weight: 700;
                padding: 0px;
                border: 1px solid {pal["border"]};
                border-radius: 5px;
            }}
            QLabel#noteReminderClock {{
                background: transparent;
                color: {pal["text"]};
                font-size: 15px;
                padding: 0px;
                min-width: 22px;
            }}
            QWidget#noteReminderRow {{
                background: transparent;
                border: none;
            }}
            QDateTimeEdit#noteCardDateTime {{
                background-color: {pal["inset"]};
                color: {pal["text"]};
                border: 1px solid {pal["border"]};
                border-radius: 4px;
                padding: 3px 6px;
                font-size: 11px;
                min-height: 24px;
            }}
            QDateTimeEdit#noteCardDateTime QLineEdit {{
                background: transparent;
                color: {pal["text"]};
                border: none;
                padding: 0px;
                selection-background-color: {pal["list_sel"]};
                selection-color: {pal["list_text"]};
            }}
            QDateTimeEdit#noteCardDateTime::drop-down {{
                background: transparent;
                width: 22px;
                border: none;
                subcontrol-origin: padding;
                subcontrol-position: center right;
            }}
            QDateTimeEdit#noteCardDateTime:disabled {{
                background-color: {pal["dt_dim_bg"]};
                color: {pal["dt_dim_fg"]};
                border: 1px solid {pal["border"]};
            }}
            QDateTimeEdit#noteCardDateTime:disabled QLineEdit {{
                background: transparent;
                color: {pal["dt_dim_fg"]};
            }}
            QCheckBox#noteReminderCheck {{
                color: {pal["text"]};
                font-size: 11px;
                background: transparent;
            }}
            QCheckBox#noteReminderCheck::indicator {{
                width: 15px;
                height: 15px;
            }}
            QCheckBox#noteReminderCheck::indicator:unchecked {{
                background-color: {pal["inset"]};
                border: 1px solid {pal["cb_border"]};
                border-radius: 3px;
            }}
            QCheckBox#noteReminderCheck::indicator:checked {{
                background-color: {pal["cb_checked"]};
                border: 1px solid {pal["cb_border"]};
                border-radius: 3px;
            }}
            QPushButton#noteCardDelete, QPushButton#noteCardSave {{
                font-size: 11px;
                padding: 4px 8px;
                border-radius: 4px;
            }}
            QPushButton#noteCardDelete {{
                background: transparent;
                color: {pal["muted"]};
                border: 1px solid {pal["border"]};
            }}
            QPushButton#noteCardSave {{
                background: {pal["inset"]};
                color: {pal["text"]};
                border: 1px solid {pal["save_border"]};
            }}
            QComboBox#noteCardColorCombo {{
                background: {pal["inset"]};
                color: {pal["text"]};
                border: 1px solid {pal["border"]};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                min-height: 22px;
            }}
            QComboBox#noteCardColorCombo::drop-down {{
                border: none;
                width: 18px;
            }}
            QComboBox#noteCardColorCombo QAbstractItemView {{
                background: {pal["list_bg"]};
                color: {pal["list_text"]};
                selection-background-color: {pal["list_sel"]};
                selection-color: {pal["list_text"]};
                outline: 0;
            }}
            QScrollArea#noteImagesScroll {{
                background: {pal["inset"]};
                border: 1px solid {pal["border"]};
                border-radius: 4px;
            }}
            QWidget#noteImagesInner {{
                background: transparent;
            }}
            QToolButton#noteImageRemoveBtn {{
                background: {pal["chrome"]};
                color: {pal["chrome_fg"]};
                border: 1px solid {pal["border"]};
                border-radius: 3px;
                font-size: 12px;
                font-weight: 700;
                padding: 0px;
                min-width: 18px;
                max-width: 18px;
                min-height: 18px;
                max-height: 18px;
            }}
            """
        )
        self._apply_folded_title_color()
        self._apply_input_placeholders(pal)
        self._position_resize_grip()

    def _end_save_flash_theme(self) -> None:
        self.apply_theme(save_flash=False)

    def _flash_save_feedback(self) -> None:
        self.apply_theme(save_flash=True)
        self._save_flash_timer.stop()
        self._save_flash_timer.start(200)

    def _apply_input_placeholders(self, pal: dict[str, str]) -> None:
        ph = QColor(pal["placeholder"])
        for w in (self._title_edit, self._body):
            pl = w.palette()
            pl.setColor(QPalette.ColorGroup.Active, QPalette.ColorRole.PlaceholderText, ph)
            pl.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.PlaceholderText, ph)
            pl.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.PlaceholderText, ph)
            w.setPalette(pl)

    def _title_color_hex(self) -> str:
        hx = str(self._card_color_hex or "").strip()
        if len(hx) == 7 and hx.startswith("#"):
            return hx
        return "#33b679"

    def _apply_title_color(self, hex_value: str):
        s = str(hex_value or "").strip()
        self._card_color_hex = s if len(s) == 7 and s.startswith("#") else "#33b679"
        self._sync_color_combo()
        self._apply_folded_title_color()

    def _sync_color_combo(self) -> None:
        cb = getattr(self, "_color_combo", None)
        if cb is None:
            return
        cb.blockSignals(True)
        idx = cb.findData(self._card_color_hex)
        cb.setCurrentIndex(idx if idx >= 0 else 0)
        cb.blockSignals(False)

    def _on_color_combo_changed(self) -> None:
        data = self._color_combo.currentData()
        if data:
            self._card_color_hex = str(data)
            self.apply_theme(save_flash=False)

    def _set_card_colour(self, hx: str) -> None:
        self._apply_title_color(hx)
        self.apply_theme(save_flash=False)

    def _popup_card_colour_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)
        sub = QMenu("Card colour", self)
        bg = self._title_color_hex()
        mpal = _card_palette(bg)
        sub.setStyleSheet(
            f"""
            QMenu {{
                background: {mpal["list_bg"]};
                color: {mpal["list_text"]};
                border: 1px solid {mpal["border"]};
            }}
            QMenu::item:selected {{
                background: {mpal["list_sel"]};
            }}
            """
        )
        for label, chx in CARD_COLOR_OPTIONS:
            act = sub.addAction(label)
            act.triggered.connect(
                lambda checked=False, h=chx: self._set_card_colour(h)
            )
        menu.addMenu(sub)
        menu.exec(global_pos)

    def _on_card_context_menu(self, pos: QPoint) -> None:
        self._popup_card_colour_menu(self.mapToGlobal(pos))

    def _on_drag_handle_context_menu(self, pos: QPoint) -> None:
        dh = self._drag_handle
        if dh is not None:
            self._popup_card_colour_menu(dh.mapToGlobal(pos))

    def _apply_folded_title_color(self):
        pal = _card_palette(self._title_color_hex())
        self._title_folded.setStyleSheet(
            f"color: {pal['text']}; font-size: 12px; font-weight: 600; background: transparent;"
        )

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(5)

        head = QHBoxLayout()
        head.setSpacing(4)
        self._drag_handle = QLabel("⠿")
        self._drag_handle.setObjectName("noteDragHandle")
        self._drag_handle.setFixedSize(22, 22)
        self._drag_handle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drag_handle.setCursor(Qt.CursorShape.SizeAllCursor)
        self._drag_handle.setToolTip("Drag to move · Right-click: card colour")
        self._drag_handle.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._drag_handle.customContextMenuRequested.connect(
            self._on_drag_handle_context_menu
        )
        head.addWidget(self._drag_handle)

        self._reminder_clock = QLabel("\U0001f550")
        self._reminder_clock.setObjectName("noteReminderClock")
        self._reminder_clock.setFixedSize(22, 22)
        self._reminder_clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._reminder_clock.setVisible(False)
        head.addWidget(self._reminder_clock)

        self._fold_btn = QToolButton()
        self._fold_btn.setObjectName("noteCardFoldBtn")
        self._fold_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fold_btn.clicked.connect(self._toggle_fold)
        head.addWidget(self._fold_btn)

        self._title_folded = QLabel()
        self._title_folded.setWordWrap(False)
        head.addWidget(self._title_folded, 1)

        self._title_edit = QLineEdit()
        self._title_edit.setObjectName("noteCardTitle")
        self._title_edit.setPlaceholderText("Title")
        head.addWidget(self._title_edit, 1)
        outer.addLayout(head)

        self._body = QPlainTextEdit()
        self._body.setObjectName("noteCardBody")
        self._body.setPlaceholderText("Write your note…")
        self._body.setMinimumHeight(80)
        self._body.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        outer.addWidget(self._body, 1)

        self._images_row = QWidget()
        self._images_row.setObjectName("noteImagesRow")
        ir = QHBoxLayout(self._images_row)
        ir.setContentsMargins(0, 0, 0, 0)
        ir.setSpacing(6)
        self._images_scroll = QScrollArea()
        self._images_scroll.setObjectName("noteImagesScroll")
        self._images_scroll.setWidgetResizable(True)
        self._images_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._images_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._images_scroll.setFixedHeight(92)
        self._images_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._images_inner = QWidget()
        self._images_inner.setObjectName("noteImagesInner")
        self._images_thumb_layout = QHBoxLayout(self._images_inner)
        self._images_thumb_layout.setContentsMargins(6, 4, 6, 4)
        self._images_thumb_layout.setSpacing(8)
        self._images_scroll.setWidget(self._images_inner)
        self._images_viewport = self._images_scroll.viewport()
        ir.addWidget(self._images_scroll, 1)
        for w in (
            self._images_scroll,
            self._images_viewport,
            self._images_inner,
        ):
            w.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            w.customContextMenuRequested.connect(self._on_images_strip_context_menu)
        outer.addWidget(self._images_row)

        self._reminder_row = QWidget()
        self._reminder_row.setObjectName("noteReminderRow")
        self._reminder_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        rem_outer = QVBoxLayout(self._reminder_row)
        rem_outer.setContentsMargins(0, 4, 0, 0)
        rem_outer.setSpacing(6)
        self._reminder_on = QCheckBox("Reminder")
        self._reminder_on.setObjectName("noteReminderCheck")
        self._reminder_on.toggled.connect(self._on_reminder_toggled)
        rem_outer.addWidget(self._reminder_on)
        self._reminder_when = QDateTimeEdit()
        self._reminder_when.setObjectName("noteCardDateTime")
        self._reminder_when.setCalendarPopup(True)
        self._reminder_when.setDisplayFormat("ddd d MMM yyyy, HH:mm")
        self._reminder_when.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._reminder_when.setMinimumWidth(300)
        self._reminder_when.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._reminder_when.dateTimeChanged.connect(self._on_reminder_datetime_changed)
        rem_outer.addWidget(self._reminder_when)
        outer.addWidget(self._reminder_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self._color_combo = QComboBox()
        self._color_combo.setObjectName("noteCardColorCombo")
        self._color_combo.setToolTip("Card colour")
        self._color_combo.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
        )
        self._color_combo.setMaximumWidth(132)
        self._color_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        for label, hx in CARD_COLOR_OPTIONS:
            self._color_combo.addItem(label, hx)
        self._color_combo.currentIndexChanged.connect(self._on_color_combo_changed)
        btn_row.addWidget(self._color_combo)
        self._save_btn = QPushButton("Save note")
        self._save_btn.setObjectName("noteCardSave")
        self._save_btn.clicked.connect(self._save_note)
        btn_row.addWidget(self._save_btn)
        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setObjectName("noteCardDelete")
        self._delete_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(self._delete_btn)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        self._resize_grip = QLabel("◢", self)
        self._resize_grip.setObjectName("noteResizeGrip")
        self._resize_grip.setFixedSize(22, 22)
        self._resize_grip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._resize_grip.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self._resize_grip.setToolTip("Drag corner to resize")

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_card_context_menu)
        self._install_raise_on_click_filters()

    def _install_raise_on_click_filters(self) -> None:
        self.installEventFilter(self)
        for w in self.findChildren(QWidget):
            w.installEventFilter(self)

    def _load_from_note(self, note: Note):
        self._title_folded.setText((note.title or "Untitled").strip() or "Untitled")
        self._title_edit.setText(note.title)
        self._body.setPlainText(note.body)
        self._expanded = note.expanded
        self._apply_title_color(note.title_color_hex)
        self._reminder_on.blockSignals(True)
        self._reminder_on.setChecked(note.reminder_at_iso is not None)
        self._reminder_on.blockSignals(False)
        when = dt.datetime.now().astimezone() + dt.timedelta(hours=1)
        if note.reminder_at_iso:
            try:
                parsed = dt.datetime.fromisoformat(note.reminder_at_iso)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=when.tzinfo)
                when = parsed
            except Exception:
                pass
        self._reminder_when.blockSignals(True)
        self._reminder_when.setDateTime(
            QDateTime(when.year, when.month, when.day, when.hour, when.minute)
        )
        self._reminder_when.blockSignals(False)
        self._reminder_when.setEnabled(note.reminder_at_iso is not None)
        self._update_reminder_clock()
        self._rebuild_image_thumbnails()

    def _rebuild_image_thumbnails(self) -> None:
        lay = self._images_thumb_layout
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        n = get_note(self._note_id)
        names = list(n.image_files) if n else []
        att = Paths.data_dir() / "note_attachments" / self._note_id
        valid_only = [fn for fn in names if (att / fn).is_file()]
        if n is not None and len(valid_only) != len(names):
            n.image_files = valid_only
            replace_note(n)
            names = valid_only
        for fn in names:
            full = att / fn
            if not full.is_file():
                continue
            cell = QWidget()
            cell.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            cell.customContextMenuRequested.connect(self._on_images_strip_context_menu)
            v = QVBoxLayout(cell)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(2)
            img = QLabel()
            img.setFixedSize(64, 64)
            img.setScaledContents(True)
            img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pix = QPixmap(str(full))
            if not pix.isNull():
                img.setPixmap(
                    pix.scaled(
                        64,
                        64,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            img.setProperty("noteImageFullPath", str(full))
            img.setToolTip(f"{fn}\nDouble-click to view full size")
            img.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            img.customContextMenuRequested.connect(self._on_images_strip_context_menu)
            img.installEventFilter(self)
            v.addWidget(img)
            rm = QToolButton()
            rm.setObjectName("noteImageRemoveBtn")
            rm.setText("×")
            rm.setToolTip("Remove image")
            rm.clicked.connect(partial(self._on_remove_note_image, fn))
            v.addWidget(rm, alignment=Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(cell)
        lay.addStretch(1)

    def _try_add_image_path(self, path: Path) -> None:
        if not path.is_file():
            return
        added = add_image_to_note(self._note_id, path)
        if added is None:
            QMessageBox.warning(
                self,
                "Image",
                "Could not add image. Use PNG, JPEG, GIF, WebP, or BMP "
                "(max 12 MB per file, up to 16 images per note).",
            )
        else:
            self._rebuild_image_thumbnails()

    def _on_add_note_image(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Add image to note",
            "",
            "Images (*.png *.jpg *.jpeg *.gif *.webp *.bmp);;All files (*.*)",
        )
        if path_str:
            self._try_add_image_path(Path(path_str))

    def _on_images_strip_context_menu(self, pos: QPoint) -> None:
        src = self.sender()
        if not isinstance(src, QWidget):
            return
        menu = QMenu(self)
        mpal = _card_palette(self._title_color_hex())
        menu.setStyleSheet(
            f"""
            QMenu {{
                background: {mpal["list_bg"]};
                color: {mpal["list_text"]};
                border: 1px solid {mpal["border"]};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 18px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background: {mpal["list_sel"]};
                color: {mpal["list_text"]};
            }}
            """
        )
        paste_act = menu.addAction("Paste from clipboard")
        add_act = menu.addAction("Add from storage")
        chosen = menu.exec(src.mapToGlobal(pos))
        if chosen is paste_act:
            if not self._try_paste_clipboard_image():
                QMessageBox.information(
                    self,
                    "Paste image",
                    "Clipboard does not contain an image.",
                )
        elif chosen is add_act:
            self._on_add_note_image()

    def _on_remove_note_image(self, filename: str) -> None:
        remove_note_image(self._note_id, filename)
        self._rebuild_image_thumbnails()

    def _open_image_preview(self, path: Path) -> None:
        if not path.is_file():
            return
        dlg = ImagePreviewDialog(self.window() or self, path)
        dlg.exec()

    def _try_paste_clipboard_image(self) -> bool:
        cb = QApplication.clipboard()
        img = cb.image()
        if img.isNull():
            pm = cb.pixmap()
            if not pm.isNull():
                img = pm.toImage()
        if img.isNull():
            return False
        n = get_note(self._note_id)
        if n is None:
            return False
        if len(n.image_files) >= MAX_IMAGES_PER_NOTE:
            QMessageBox.warning(
                self,
                "Image",
                f"Each note allows at most {MAX_IMAGES_PER_NOTE} images.",
            )
            return True
        name = f"{uuid.uuid4().hex}.png"
        path = Paths.note_attachments_dir(self._note_id) / name
        if not img.save(str(path), "PNG"):
            QMessageBox.warning(self, "Image", "Could not save clipboard image.")
            return True
        if not register_note_attachment_file(self._note_id, name):
            try:
                path.unlink(missing_ok=True)
            except TypeError:
                if path.is_file():
                    path.unlink()
            QMessageBox.warning(self, "Image", "Could not attach clipboard image.")
            return True
        self._rebuild_image_thumbnails()
        return True

    def _format_reminder_fire_tooltip(self) -> str:
        qdt = self._reminder_when.dateTime().toPyDateTime()
        tz = dt.datetime.now().astimezone().tzinfo
        if qdt.tzinfo is None:
            qdt = qdt.replace(tzinfo=tz)
        local = qdt.astimezone(tz)
        return f"Reminder will ring: {local.strftime('%a %d %b %Y, %H:%M')}"

    def _update_reminder_clock(self) -> None:
        rc = getattr(self, "_reminder_clock", None)
        if rc is None:
            return
        on = self._reminder_on.isChecked()
        rc.setVisible(on)
        if on:
            rc.setToolTip(self._format_reminder_fire_tooltip())
        else:
            rc.setToolTip("")

    def eventFilter(self, obj, event):
        vp = getattr(self, "_images_viewport", None)
        if vp is not None and obj is vp:
            et = event.type()
            if et == QEvent.Type.DragEnter:
                de = event
                if de.mimeData().hasUrls():
                    de.acceptProposedAction()
                    return True
            if et == QEvent.Type.DragMove:
                de = event
                if de.mimeData().hasUrls():
                    de.acceptProposedAction()
                    return True
            if et == QEvent.Type.Drop:
                de = event
                for url in de.mimeData().urls():
                    p = Path(url.toLocalFile())
                    if p.is_file():
                        self._try_add_image_path(p)
                return True
        if self._expanded and event.type() == QEvent.Type.KeyPress:
            ke = event
            if ke.matches(QKeySequence.StandardKey.Paste):
                if self._try_paste_clipboard_image():
                    return True
        if event.type() == QEvent.Type.MouseButtonDblClick:
            p = obj.property("noteImageFullPath")
            if p:
                self._open_image_preview(Path(str(p)))
                return True
        if event.type() == QEvent.Type.MouseButtonPress:
            # Avoid raising the card on thumbnail presses (double-click would fire twice).
            if not obj.property("noteImageFullPath"):
                self.raise_()
        # Use getattr: Qt may deliver events before all watched widgets exist, or obj may
        # not be the drag handle (avoid touching self._resize_grip unless it is set).
        dh = getattr(self, "_drag_handle", None)
        if dh is not None and obj is dh:
            et = event.type()
            if et == QEvent.Type.MouseButtonPress:
                me = event
                if me.button() == Qt.MouseButton.LeftButton:
                    self._drag_active = True
                    self._press_global = me.globalPosition().toPoint()
                    self._start_pos = self.pos()
                    self.raise_()
                    dh.grabMouse()
                    return True
            elif et == QEvent.Type.MouseMove:
                me = event
                if self._drag_active and (me.buttons() & Qt.MouseButton.LeftButton):
                    delta = me.globalPosition().toPoint() - self._press_global
                    new_pos = self._start_pos + delta
                    new_pos.setX(max(0, new_pos.x()))
                    new_pos.setY(max(0, new_pos.y()))
                    self.move(new_pos)
                    self._canvas.resize_to_fit_cards()
                    return True
            elif et == QEvent.Type.MouseButtonRelease:
                me = event
                if me.button() == Qt.MouseButton.LeftButton and self._drag_active:
                    self._drag_active = False
                    try:
                        dh.releaseMouse()
                    except Exception:
                        pass
                    patch_note_canvas_position(self._note_id, float(self.x()), float(self.y()))
                    self._canvas.resize_to_fit_cards()
                    return True
        rg = getattr(self, "_resize_grip", None)
        if rg is not None and obj is rg and self._expanded:
            et = event.type()
            if et == QEvent.Type.MouseButtonPress:
                me = event
                if me.button() == Qt.MouseButton.LeftButton:
                    self._resize_active = True
                    self._resize_press = me.globalPosition().toPoint()
                    self._resize_start_geom = self.geometry()
                    self.raise_()
                    rg.grabMouse()
                    return True
            elif et == QEvent.Type.MouseMove:
                me = event
                if self._resize_active and (me.buttons() & Qt.MouseButton.LeftButton):
                    delta = me.globalPosition().toPoint() - self._resize_press
                    nw = max(NOTE_MIN_W, min(720, self._resize_start_geom.width() + delta.x()))
                    nh = max(NOTE_MIN_H, min(900, self._resize_start_geom.height() + delta.y()))
                    self.resize(nw, nh)
                    self._canvas.resize_to_fit_cards()
                    return True
            elif et == QEvent.Type.MouseButtonRelease:
                me = event
                if me.button() == Qt.MouseButton.LeftButton and self._resize_active:
                    self._resize_active = False
                    try:
                        rg.releaseMouse()
                    except Exception:
                        pass
                    patch_note_card_size(
                        self._note_id, float(self.width()), float(self.height())
                    )
                    self._canvas.resize_to_fit_cards()
                    return True
        return super().eventFilter(obj, event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._position_resize_grip()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._position_resize_grip()

    def _position_resize_grip(self) -> None:
        rg = getattr(self, "_resize_grip", None)
        if rg is None or not rg.isVisible():
            return
        m = 2
        rg.move(self.width() - rg.width() - m, self.height() - rg.height() - m)
        rg.raise_()

    def _apply_fold_state(self):
        exp = self._expanded
        n = get_note(self._note_id)
        w = int(n.card_width) if n else NOTE_DEFAULT_W
        h = int(n.card_height) if n else NOTE_DEFAULT_H
        w = max(NOTE_MIN_W, min(720, w))
        h = max(NOTE_MIN_H, min(900, h))
        self._fold_btn.setText("▼" if exp else "▶")
        self._title_folded.setVisible(not exp)
        self._title_edit.setVisible(exp)
        self._body.setVisible(exp)
        self._images_row.setVisible(exp)
        self._reminder_row.setVisible(exp)
        self._color_combo.setVisible(exp)
        self._save_btn.setVisible(exp)
        self._delete_btn.setVisible(exp)
        self._resize_grip.setVisible(exp)
        if not exp:
            self.setMinimumWidth(w)
            self.setMaximumWidth(16777215)
            self.setMinimumHeight(52)
            self.setMaximumHeight(52)
            self.resize(w, 52)
        else:
            self.setMaximumHeight(16777215)
            self.setMinimumHeight(NOTE_MIN_H)
            self.setMinimumWidth(NOTE_MIN_W)
            self.setMaximumWidth(16777215)
            self.resize(w, h)
        self._update_reminder_clock()
        self._position_resize_grip()

    def _toggle_fold(self):
        self._expanded = not self._expanded
        patch_note_expanded(self._note_id, self._expanded)
        self._apply_fold_state()
        self._canvas.resize_to_fit_cards()
        if self._expanded:
            QTimer.singleShot(0, self._reflow_height)

    def _reflow_height(self):
        self._canvas.resize_to_fit_cards()

    def _save_note(self):
        n = get_note(self._note_id)
        if n is None:
            return
        n.title = self._title_edit.text()
        n.body = self._body.toPlainText()
        n.title_color_hex = self._title_color_hex()
        n.expanded = self._expanded
        n.card_width = float(self.width())
        if self._expanded:
            n.card_height = float(self.height())
        replace_note(n)
        self._title_folded.setText((n.title or "Untitled").strip() or "Untitled")
        refresh_note_reminder_title(n)
        if self._reminder_on.isChecked():
            sync_note_reminder(n)
            self._scheduler.refresh()
        self._update_reminder_clock()
        self._flash_save_feedback()

    def _refresh_reminder_gate(self):
        n = get_note(self._note_id)
        if n is None:
            self._update_reminder_clock()
            return
        self._reminder_on.blockSignals(True)
        self._reminder_on.setChecked(n.reminder_at_iso is not None)
        self._reminder_on.blockSignals(False)
        self._reminder_when.setEnabled(n.reminder_at_iso is not None)
        self._update_reminder_clock()

    def _on_reminder_toggled(self, checked: bool):
        n = get_note(self._note_id)
        if n is None:
            return
        self._reminder_when.setEnabled(checked)
        if checked:
            qdt = self._reminder_when.dateTime().toPyDateTime()
            if qdt.tzinfo is None:
                qdt = qdt.replace(tzinfo=dt.datetime.now().astimezone().tzinfo)
            n.reminder_at_iso = qdt.isoformat()
        else:
            n.reminder_at_iso = None
        sync_note_reminder(n)
        self._refresh_reminder_gate()
        self._scheduler.refresh()

    def _on_reminder_datetime_changed(self):
        if not self._reminder_on.isChecked():
            return
        n = get_note(self._note_id)
        if n is None:
            return
        qdt = self._reminder_when.dateTime().toPyDateTime()
        tz = dt.datetime.now().astimezone().tzinfo
        if qdt.tzinfo is None:
            qdt = qdt.replace(tzinfo=tz)
        n.reminder_at_iso = qdt.isoformat()
        sync_note_reminder(n)
        self._refresh_reminder_gate()
        self._scheduler.refresh()

    def _on_delete(self):
        title = self._title_edit.text().strip() or "this note"
        if (
            QMessageBox.question(
                self,
                "Delete note",
                f"Delete “{title}”?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self._host.delete_card(self._note_id)

    def cleanup_unregister(self):
        self._canvas.unregister_card(self._note_id)


class NotesWidget(QWidget):
    def __init__(self, scheduler: AlarmScheduler, parent=None):
        super().__init__(parent)
        self._scheduler = scheduler
        self._canvas: NotesCanvas | None = None
        self._cards: dict[str, NoteCard] = {}
        self._build_ui()
        self.rebuild()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        bar = QHBoxLayout()
        bar.addStretch()
        add_btn = QPushButton("+ New note")
        add_btn.clicked.connect(self._on_new_note)
        bar.addWidget(add_btn)
        layout.addLayout(bar)

        scroll = QScrollArea()
        # False: keep canvas larger than the viewport so absolute-positioned cards stay visible.
        scroll.setWidgetResizable(False)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll = scroll
        self._canvas = NotesCanvas()
        scroll.setWidget(self._canvas)
        layout.addWidget(scroll, 1)

    def rebuild(self):
        if self._canvas is None:
            return
        self._canvas.clear_registry()
        for card in list(self._cards.values()):
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()
        notes = sorted(load_notes(), key=lambda n: n.updated_at_iso, reverse=True)
        for note in notes:
            card = NoteCard(note, self._scheduler, self._canvas, self)
            self._cards[note.id] = card
            card.show()
            card.raise_()
        self._canvas.resize_to_fit_cards()
        self._canvas.show()

    def delete_card(self, note_id: str):
        if delete_note(note_id):
            self._scheduler.refresh()
            self.rebuild()

    def _on_new_note(self):
        notes = load_notes()
        col = len(notes) % 4
        row = len(notes) // 4
        n = new_note(
            canvas_x=float(CANVAS_MARGIN + col * (NOTE_DEFAULT_W + 24)),
            canvas_y=float(CANVAS_MARGIN + row * (NOTE_DEFAULT_H + 24)),
        )
        replace_note(n)
        self._scheduler.refresh()
        self.rebuild()
        self.focus_note(n.id)

    def focus_note(self, note_id: str):
        card = self._cards.get(note_id)
        if card is None:
            self.rebuild()
            card = self._cards.get(note_id)
        if card is None or self._scroll is None:
            return
        card.show()
        card.raise_()
        self._scroll.ensureWidgetVisible(card)
        if not card._expanded:
            card._toggle_fold()

    def apply_theme(self):
        if self._canvas:
            self._canvas._apply_bg()
        for card in self._cards.values():
            card.apply_theme()
