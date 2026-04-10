"""
windows_startup.py — HKCU Run entry for launch at Windows startup.

No admin required. No-op on non-Windows platforms.
"""
from __future__ import annotations

import platform
import sys
from pathlib import Path

_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "TrayPilot"


def is_run_at_startup_enabled() -> bool:
    if platform.system() != "Windows":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH) as key:
            winreg.QueryValueEx(key, _VALUE_NAME)
        return True
    except OSError:
        return False


def set_run_at_startup(enabled: bool) -> None:
    if platform.system() != "Windows":
        return
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _REG_PATH,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            if enabled:
                if getattr(sys, "frozen", False):
                    cmd = f'"{sys.executable}"'
                else:
                    main_py = Path(__file__).resolve().parent / "main.py"
                    cmd = f'"{sys.executable}" "{main_py}"'
                winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, _VALUE_NAME)
                except FileNotFoundError:
                    pass
    except OSError:
        return
