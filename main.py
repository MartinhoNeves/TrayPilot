import sys
import threading



from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from colour_theme import set_theme_mode as set_ui_theme_mode
from alarm_scheduler import AlarmScheduler
from gmail_client import GmailClient
from google_client import GoogleClient
from paths import Paths
from settings import get_theme_mode

# Display / About tab — bump when you ship a release (also update changelog in version.md if you keep it).
APP_VERSION = "1.2"

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("TrayPilot")
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("mn-projects")
    app.setQuitOnLastWindowClosed(False)

    app.setWindowIcon(QIcon(str(Paths.assets_dir() / "app.ico")))
    set_ui_theme_mode(get_theme_mode())

    client = GoogleClient()
    alarm_scheduler = AlarmScheduler()
    gmail_client = GmailClient(client)

    client.auth_required.connect(
        lambda: threading.Thread(target=client.run_auth_flow, daemon=True).start()
    )

    # Surface auth/API errors as tray balloon messages so they're never silent.
    def _on_client_error(msg: str):
        print(f"[TrayPilot] GoogleClient error: {msg}", file=sys.stderr)

    client.error.connect(_on_client_error)

    from tray import TrayIcon  # deferred — tray imports popup
    tray = TrayIcon(app, client, alarm_scheduler, gmail_client=gmail_client)
    tray.show()
    alarm_scheduler.start()

    # Run in background — discovery doc fetch can take 5-20 s on first call.
    # Tray appears immediately; events load when auth completes.
    threading.Thread(target=client.ensure_authenticated, daemon=True).start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
