"""
colour_theme.py — central theme palette and mode state.

This module is the single source of truth for UI colours.
"""
from __future__ import annotations

from typing import Literal

ThemeMode = Literal["dark", "light"]

THEME_DARK: dict[str, str] = {
    "bg": "#1a1a2e",
    "text": "#ddd",
    "accent": "#e8922a",
    "danger": "#ea4335",
    "dim": "#555",
    "border": "rgba(255,255,255,0.06)",
    "titlebar": "#141428",
    "muted": "#444",
    "scroll_handle": "#333",
    "tab_hover": "#888",
    "status_connected": "#34a853",
    "calendar_text": "#aaa",
    "calendar_other_month": "#2a2a42",
    "calendar_nav_arrow": "#b8bec9",
    "calendar_spin_text": "#e0e0e0",
    "calendar_tool_hover_bg": "rgba(255,255,255,0.06)",
    "calendar_selected_overlay": "#26e8922a",
    "calendar_grid": "#2f3446",
    "row_hover_bg": "rgba(255,255,255,0.04)",
    "row_selected_bg": "rgba(232,146,42,0.08)",
    "agenda_btn_bg": "rgba(232,146,42,0.12)",
    "agenda_btn_bg_hover": "rgba(232,146,42,0.20)",
    "agenda_btn_border": "rgba(232,146,42,0.3)",
    "agenda_btn_border_hover": "rgba(232,146,42,0.5)",
    "action_btn_border": "rgba(255,255,255,0.12)",
    "action_btn_border_hover": "rgba(255,255,255,0.25)",
    "danger_btn_border": "rgba(234,67,53,0.3)",
    "danger_btn_border_hover": "rgba(234,67,53,0.5)",
    "danger_btn_bg_hover": "rgba(234,67,53,0.08)",
    "popup_shadow": "rgba(0,0,0,0.70)",
    "popup_line_danger": "rgba(234,67,53,0.25)",
}

THEME_LIGHT: dict[str, str] = {
    "bg": "#e9edf5",
    "text": "#111827",
    "accent": "#a85a00",
    "danger": "#b42318",
    "dim": "#374151",
    "border": "rgba(17,24,39,0.24)",
    "titlebar": "#d5dcea",
    "muted": "#4b5563",
    "scroll_handle": "#6b7280",
    "tab_hover": "#1f2937",
    "status_connected": "#166534",
    "calendar_text": "#1f2937",
    "calendar_other_month": "#9ca3af",
    "calendar_nav_arrow": "#9ca3af",
    "calendar_spin_text": "#111827",
    "calendar_tool_hover_bg": "rgba(17,24,39,0.10)",
    "calendar_selected_overlay": "#40a85a00",
    "calendar_grid": "#c3cad6",
    "row_hover_bg": "rgba(17,24,39,0.08)",
    "row_selected_bg": "rgba(168,90,0,0.16)",
    "agenda_btn_bg": "rgba(168,90,0,0.12)",
    "agenda_btn_bg_hover": "rgba(168,90,0,0.22)",
    "agenda_btn_border": "rgba(168,90,0,0.55)",
    "agenda_btn_border_hover": "rgba(168,90,0,0.80)",
    "action_btn_border": "rgba(17,24,39,0.28)",
    "action_btn_border_hover": "rgba(17,24,39,0.52)",
    "danger_btn_border": "rgba(180,35,24,0.45)",
    "danger_btn_border_hover": "rgba(180,35,24,0.72)",
    "danger_btn_bg_hover": "rgba(180,35,24,0.16)",
    "popup_shadow": "rgba(0,0,0,0.45)",
    "popup_line_danger": "rgba(180,35,24,0.42)",
}

_MODE: ThemeMode = "dark"


def theme_mode() -> ThemeMode:
    return _MODE


def set_theme_mode(mode: ThemeMode) -> ThemeMode:
    global _MODE
    _MODE = "light" if mode == "light" else "dark"
    return _MODE


def toggle_theme_mode() -> ThemeMode:
    return set_theme_mode("light" if _MODE == "dark" else "dark")


def c(name: str) -> str:
    palette = THEME_LIGHT if _MODE == "light" else THEME_DARK
    return palette[name]

