"""
dialog_about.py — About TrayPilot (modal dialog + shared `AboutPanel` for the About tab).

Edit ABOUT_TITLE / ABOUT_BODY below to customize copy.
Logo: Assets/app.png (scaled, transparent); swap the file to rebrand without code changes.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from colour_theme import c
from paths import Paths

# Left : right column stretch (≈25% : 75%)
_LOGO_STRETCH = 1
_TEXT_STRETCH = 3


class _ScaledLogoLabel(QLabel):
    """QLabel that rescales its pixmap to fill available width while keeping aspect ratio."""

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._source = pixmap
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(64, 64)
        # Set initial pixmap so layout has something to measure
        self.setPixmap(self._source)

    def sizeHint(self):
        return self._source.size()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        if not self._source.isNull() and w > 0 and h > 0:
            scaled = self._source.scaled(
                w, h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.setPixmap(scaled)

# ── Customize this text anytime ───────────────────────────────────────────────
ABOUT_TITLE = "About TrayPilot"

ABOUT_BODY = """\
TrayPilot is a lightweight Windows tray application built to keep your Google Calendar and Gmail within arm's reach — without opening a browser.

From the tray icon you can glance at today's events, spot urgent ones at a glance, browse and read unread Gmail messages, manage local alarms with custom sounds and snooze, and create or edit calendar events — all without leaving the desktop.

Built with Python and PyQt6.
Part of the mn-projects suite — small tools made with care.

© mn-projects.eu\
"""


class AboutPanel(QWidget):
    """Logo + title + version + body — used in the main-window About tab and in `AboutDialog`."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("aboutPanelRoot")

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)

        logo_path = Path(Paths.assets_dir()) / "app.png"
        self._logo_lbl: _ScaledLogoLabel | None = None
        has_logo = False
        if logo_path.is_file():
            pix = QPixmap(str(logo_path))
            if not pix.isNull():
                self._logo_lbl = _ScaledLogoLabel(pix)
                self._logo_lbl.setObjectName("aboutLogo")
                has_logo = True

        if has_logo and self._logo_lbl is not None:
            left_col = QWidget()
            left_col.setObjectName("aboutLogoColumn")
            ll = QVBoxLayout(left_col)
            ll.setContentsMargins(0, 0, 0, 0)
            ll.setSpacing(0)
            ll.addStretch(1)
            ll.addWidget(self._logo_lbl, 0, Qt.AlignmentFlag.AlignHCenter)
            ll.addStretch(1)
            row.addWidget(left_col, _LOGO_STRETCH)

        right_col = QWidget()
        right_col.setObjectName("aboutTextColumn")
        rl = QVBoxLayout(right_col)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(10)

        self._title_lbl = QLabel(ABOUT_TITLE)
        self._title_lbl.setObjectName("aboutTitle")
        self._title_lbl.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._title_lbl.setWordWrap(True)
        rl.addWidget(self._title_lbl)

        self._version_lbl = QLabel()
        self._version_lbl.setObjectName("aboutVersion")
        self._version_lbl.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        rl.addWidget(self._version_lbl)
        self.refresh_version()

        self._body = QTextBrowser()
        self._body.setObjectName("aboutBody")
        self._body.setReadOnly(True)
        self._body.setOpenExternalLinks(True)
        self._body.setPlainText(ABOUT_BODY.strip())
        rl.addWidget(self._body, 1)

        row.addWidget(right_col, _TEXT_STRETCH if has_logo else 1)

    def refresh_version(self) -> None:
        from main import APP_VERSION

        self._version_lbl.setText(f"Version {APP_VERSION}")

    def apply_theme(self) -> None:
        self.setStyleSheet(
            f"""
            QWidget#aboutPanelRoot {{
                background: transparent;
                color: {c("text")};
                font-family: 'Segoe UI', sans-serif;
            }}
            QWidget#aboutLogoColumn {{
                background: transparent;
            }}
            QLabel#aboutLogo {{
                background: transparent;
                border: none;
            }}
            QWidget#aboutTextColumn {{
                background: transparent;
            }}
            QLabel#aboutTitle {{
                font-size: 16px;
                font-weight: 700;
                color: {c("accent")};
                background: transparent;
            }}
            QLabel#aboutVersion {{
                font-size: 11px;
                color: {c("dim")};
                background: transparent;
            }}
            QTextBrowser#aboutBody {{
                background: {c("titlebar")};
                color: {c("text")};
                border: 1px solid {c("border")};
                border-radius: 6px;
                padding: 10px;
                font-size: 13px;
            }}
            """
        )


class AboutDialog(QDialog):
    """Modal About window themed for the current light/dark palette."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(ABOUT_TITLE)
        self.setMinimumSize(480, 320)
        self.resize(560, 380)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 14)
        outer.setSpacing(0)

        self._panel = AboutPanel(self)
        outer.addWidget(self._panel, 1)

        ok_row = QHBoxLayout()
        ok_row.addStretch(1)
        ok = QPushButton("OK")
        ok.setObjectName("aboutOkBtn")
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.clicked.connect(self.accept)
        ok_row.addWidget(ok)
        outer.addLayout(ok_row)

        self._apply_theme()

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            f"""
            QDialog {{
                background: {c("bg")};
                color: {c("text")};
                font-family: 'Segoe UI', sans-serif;
            }}
            QPushButton#aboutOkBtn {{
                background: {c("agenda_btn_bg")};
                border: 1px solid {c("agenda_btn_border")};
                border-radius: 6px;
                color: {c("accent")};
                font-size: 12px;
                padding: 6px 22px;
                min-width: 72px;
            }}
            QPushButton#aboutOkBtn:hover {{
                background: {c("agenda_btn_bg_hover")};
                border-color: {c("agenda_btn_border_hover")};
            }}
            """
        )
        self._panel.apply_theme()
