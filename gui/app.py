import sys
import yaml
from pathlib import Path
import customtkinter as ctk

from gui import i18n

_PROJECT_ROOT = Path(__file__).parent.parent


class App(ctk.CTk):
    def __init__(self):
        # Load config and language before creating any widget
        self.project_root: Path = _PROJECT_ROOT
        self.cli_root:     Path = _PROJECT_ROOT.parent / "CrunchyExporter-cli"
        self.config_path: Path  = _PROJECT_ROOT / "config.yaml"
        self.cfg: dict          = self._load_config()

        i18n.load(self.cfg.get("ui", {}).get("language", "en"))

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        super().__init__()

        self.title(i18n.t("app_title"))
        self.geometry("980x700")
        self.minsize(820, 580)
        self._set_icon()
        self._build_ui()
        self._setup_tray()

    # ------------------------------------------------------------------ config

    def _load_config(self) -> dict:
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def save_config(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self.cfg, f, allow_unicode=True,
                      default_flow_style=False, sort_keys=False)
        # Always refresh the status bar after saving
        self.refresh_status()

    def refresh_status(self) -> None:
        if hasattr(self, "statusbar"):
            self.statusbar.refresh()

    # ------------------------------------------------------------------ tray

    def _setup_tray(self) -> None:
        self.tray = None
        self.apply_tray_setting()

    def apply_tray_setting(self) -> None:
        """Start or stop the tray icon based on the current config value.
        Safe to call at any time — handles transitions in both directions."""
        enabled = self.cfg.get("ui", {}).get("tray_enabled", False)

        if enabled:
            if self.tray is None:
                from gui.tray import TrayIcon
                self.tray = TrayIcon(self)
                self.tray.start()
            self.protocol("WM_DELETE_WINDOW", self._on_close_btn)
        else:
            if self.tray is not None:
                self.tray.stop()
                self.tray = None
            # Restore normal close behaviour
            self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _on_close_btn(self) -> None:
        """Hide window to tray. The app keeps running; Exit from tray to quit."""
        self.withdraw()
        if self.tray:
            self.tray.notify(i18n.t("tray_minimized_hint"))

    # ------------------------------------------------------------------ icon

    def _set_icon(self) -> None:
        icon_png = self.project_root / "crunchyexporterlogo.png"
        if not icon_png.exists():
            return
        try:
            from PIL import Image, ImageTk
            img = Image.open(icon_png)

            ico_path = icon_png.with_suffix(".ico")
            if not ico_path.exists():
                img.save(str(ico_path), format="ICO",
                         sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])

            self.iconbitmap(str(ico_path))
            self._icon_photo = ImageTk.PhotoImage(img.resize((32, 32)))
            self.iconphoto(True, self._icon_photo)
        except Exception:
            pass

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        from gui.tabs.tab_fetch    import FetchTab
        from gui.tabs.tab_status   import StatusTab
        from gui.tabs.tab_export   import ExportTab
        from gui.tabs.tab_config   import ConfigTab
        from gui.tabs.tab_schedule import ScheduleTab
        from gui.statusbar         import StatusBar

        # --- Navigation bar (topmost element — no header above it) ---
        nav_bg = ctk.CTkFrame(self, height=48, corner_radius=0,
                              fg_color=("gray80", "gray17"))
        nav_bg.pack(fill="x")
        nav_bg.pack_propagate(False)

        nav_values = [
            i18n.t("nav_sync"),
            i18n.t("nav_library"),
            i18n.t("nav_export"),
            i18n.t("nav_schedule"),
            i18n.t("nav_settings"),
        ]
        self._nav_keys = {
            i18n.t("nav_sync"):     "sync",
            i18n.t("nav_library"):  "library",
            i18n.t("nav_export"):   "export",
            i18n.t("nav_schedule"): "schedule",
            i18n.t("nav_settings"): "settings",
        }

        self._nav = ctk.CTkSegmentedButton(
            nav_bg,
            values=nav_values,
            command=self._on_nav,
            font=ctk.CTkFont(size=13),
        )
        self._nav.pack(fill="x", padx=20, pady=8)
        self._nav.set(nav_values[0])

        # --- Status bar (below nav) ---
        self.statusbar = StatusBar(self, self)
        self.statusbar.pack(fill="x")

        # --- Content area: all frames stacked, raised by nav ---
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        sync_f     = ctk.CTkFrame(content, fg_color="transparent")
        library_f  = ctk.CTkFrame(content, fg_color="transparent")
        export_f   = ctk.CTkFrame(content, fg_color="transparent")
        schedule_f = ctk.CTkFrame(content, fg_color="transparent")
        settings_f = ctk.CTkFrame(content, fg_color="transparent")

        for f in (sync_f, library_f, export_f, schedule_f, settings_f):
            f.grid(row=0, column=0, sticky="nsew")

        self._frames = {
            "sync":     sync_f,
            "library":  library_f,
            "export":   export_f,
            "schedule": schedule_f,
            "settings": settings_f,
        }

        self.tab_fetch    = FetchTab(   sync_f,     self)
        self.tab_status   = StatusTab(  library_f,  self)
        self.tab_export   = ExportTab(  export_f,   self)
        self.tab_schedule = ScheduleTab(schedule_f, self)
        self.tab_config   = ConfigTab(  settings_f, self)

        self._show("sync")

    # ------------------------------------------------------------------ nav

    def _on_nav(self, value: str) -> None:
        key = self._nav_keys.get(value, "sync")
        self._show(key)
        # Refresh export tab status indicators when the user opens it
        if key == "export":
            self.tab_export.refresh_status()

    def _show(self, key: str) -> None:
        self._frames[key].tkraise()
