"""
System tray icon manager.

Behaviour:
  - Icon appears in the notification area as soon as the app starts.
  - Closing the window (X button) hides it; the app keeps running.
  - Double-clicking the tray icon restores the window.
  - Right-click menu: Open | Sync Now | ── | Exit

"Sync Now" runs a background sync without opening the window.
  It shows a Windows toast notification when done.

Thread model:
  pystray runs its event loop in a daemon thread.
  All Tkinter calls (deiconify, refresh_status …) are marshalled back to
  the main thread via app.after(0, callback) — the only safe way.
"""

import threading
from pathlib import Path

import pystray
from PIL import Image

from gui import i18n


class TrayIcon:
    def __init__(self, app) -> None:
        self.app = app
        self._icon: pystray.Icon | None = None
        self._syncing = False   # guard against concurrent tray syncs

    # ------------------------------------------------------------------ public

    def start(self) -> None:
        """Create and show the tray icon. Non-blocking (runs in daemon thread)."""
        img = self._load_image()
        menu = pystray.Menu(
            pystray.MenuItem(i18n.t("tray_open"),     self._on_open, default=True),
            pystray.MenuItem(i18n.t("tray_sync_now"), self._on_sync_now),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(i18n.t("tray_exit"),     self._on_exit),
        )
        self._icon = pystray.Icon(
            "CrunchyExporter",
            img,
            i18n.t("app_title"),
            menu,
        )
        threading.Thread(target=self._icon.run, daemon=True).start()

    def stop(self) -> None:
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass

    def notify(self, message: str, title: str | None = None) -> None:
        """Show a Windows toast notification (best-effort)."""
        if not self._icon:
            return
        try:
            self._icon.notify(message, title or i18n.t("app_title"))
        except Exception:
            pass

    # ------------------------------------------------------------------ menu callbacks (tray thread)

    def _on_open(self, icon=None, item=None) -> None:
        self.app.after(0, self._show_window)

    def _on_sync_now(self, icon=None, item=None) -> None:
        if self._syncing:
            return
        # The CLI reads etp_rt from config.yaml — no need to pass it here
        if not self.app.cfg.get("crunchyroll", {}).get("etp_rt", "").strip():
            self.notify(i18n.t("tray_sync_no_cookie"))
            return

        self._syncing = True
        self.notify(i18n.t("tray_sync_started"))
        self._run_sync()

    def _on_exit(self, icon=None, item=None) -> None:
        self.app.after(0, self._do_exit)

    # ------------------------------------------------------------------ helpers (main thread)

    def _show_window(self) -> None:
        self.app.deiconify()
        self.app.lift()
        self.app.focus_force()

    def _do_exit(self) -> None:
        self.stop()
        self.app.destroy()

    # ------------------------------------------------------------------ background sync

    def _run_sync(self) -> None:
        """
        Delegate entirely to the CLI's sync command (fetch + export).
        Runs as a subprocess so we reuse the CLI as-is without reimplementing anything.
        """
        import sys
        import subprocess

        cmd = [
            sys.executable,
            str(self.app.project_root / "src" / "main.py"),
            "-c", str(self.app.config_path),
            "sync",
        ]

        def run() -> None:
            result = subprocess.run(cmd, capture_output=True, text=True)
            self._syncing = False
            if result.returncode == 0:
                self.app.after(0, self.app.refresh_status)
                self.app.after(0, self.app.tab_status.refresh)
                self.notify(i18n.t("tray_sync_done"))
            else:
                self.notify(i18n.t("tray_sync_failed"))

        threading.Thread(target=run, daemon=True).start()

    # ------------------------------------------------------------------ icon image

    def _load_image(self) -> Image.Image:
        png = self.app.project_root / "crunchyexporterlogo.png"
        if png.exists():
            try:
                return Image.open(png).convert("RGBA")
            except Exception:
                pass
        # Fallback: plain coloured square so the tray always has an icon
        img = Image.new("RGBA", (64, 64), color="#1a56db")
        return img
