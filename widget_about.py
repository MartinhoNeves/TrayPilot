"""
widget_about.py — Main-window About tab (same content as `AboutDialog`, scrollable).
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget

from colour_theme import c
from dialog_about import AboutPanel


class AboutTabWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._panel = AboutPanel()
        scroll.setWidget(self._panel)
        lay.addWidget(scroll)
        self._scroll = scroll
        self.apply_theme()

    def on_tab_activated(self) -> None:
        self._panel.refresh_version()

    def apply_theme(self) -> None:
        self._panel.apply_theme()
        self._scroll.setStyleSheet(
            f"""
            QScrollArea {{
                background: {c("bg")};
                border: none;
            }}
            """
        )
