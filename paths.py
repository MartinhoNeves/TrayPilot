"""
paths.py — All file-system path resolution for TrayPilot.

Rules:
- Mutable runtime data  → %LOCALAPPDATA%\\mn-projects\\TrayPilot\\
- Static assets         → next to the executable (packaged) or project root (dev)
"""
import sys
from pathlib import Path

import platformdirs


class Paths:
    _app_name = "TrayPilot"
    _app_author = "mn-projects"

    # ── Runtime data dir (AppData) ─────────────────────────────────────────────

    @classmethod
    def data_dir(cls) -> Path:
        """
        %LOCALAPPDATA%\\mn-projects\\TrayPilot\\
        Created on first access.
        """
        d = Path(platformdirs.user_data_dir(cls._app_name, cls._app_author, roaming=False))
        d.mkdir(parents=True, exist_ok=True)
        return d

    @classmethod
    def token_json(cls) -> Path:
        return cls.data_dir() / "token.json"

    @classmethod
    def settings_json(cls) -> Path:
        return cls.data_dir() / "settings.json"

    @classmethod
    def alarms_json(cls) -> Path:
        return cls.data_dir() / "alarms.json"

    # ── Static assets ──────────────────────────────────────────────────────────

    @classmethod
    def assets_dir(cls) -> Path:
        return cls._project_root() / "Assets"

    @classmethod
    def credentials_json(cls) -> Path:
        """
        credentials.json lives in the user data directory (AppData) in all modes.
        Users must place their Google API credentials file there before first launch.
        """
        return cls.data_dir() / "credentials.json"

    # ── Internals ─────────────────────────────────────────────────────────────

    @classmethod
    def _project_root(cls) -> Path:
        """
        Dev:    directory containing main.py.
        Frozen: sys._MEIPASS — the _internal/ bundle directory in PyInstaller 6.x
                where all data files (assets, etc.) are placed.
        """
        if getattr(sys, "frozen", False):
            return Path(sys._MEIPASS)
        return Path(__file__).resolve().parent
