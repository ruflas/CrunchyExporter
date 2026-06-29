import webbrowser
import customtkinter as ctk

from gui import i18n
from gui.version import __version__, RELEASES_URL


class ConfigTab:
    def __init__(self, frame: ctk.CTkFrame, app) -> None:
        self.app = app
        self.frame = frame
        self._entries: dict[str, ctk.CTkEntry] = {}
        self._build(frame)
        self._load_values()
        self._toggle_mal_secret()

    # ------------------------------------------------------------------ build

    def _build(self, f: ctk.CTkFrame) -> None:
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(f)
        scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 0))
        scroll.columnconfigure(1, weight=1)

        row = [0]

        def section(key: str) -> None:
            ctk.CTkLabel(
                scroll, text=i18n.t(key),
                font=ctk.CTkFont(size=13, weight="bold"), anchor="w",
            ).grid(row=row[0], column=0, columnspan=3, sticky="w",
                   padx=8, pady=(14, 4))
            row[0] += 1

        def note(key: str) -> None:
            ctk.CTkLabel(
                scroll, text=i18n.t(key),
                font=ctk.CTkFont(size=10),
                text_color=("gray50", "gray60"),
                anchor="w", wraplength=720,
            ).grid(row=row[0], column=0, columnspan=3, sticky="w",
                   padx=8, pady=(0, 6))
            row[0] += 1

        def field(label_key: str, entry_key: str,
                  placeholder_key: str = "", secret: bool = False) -> None:
            placeholder = i18n.t(placeholder_key) if placeholder_key else ""
            ctk.CTkLabel(scroll, text=i18n.t(label_key) + ":",
                         anchor="e").grid(row=row[0], column=0,
                                          sticky="e", padx=(8, 8), pady=2)
            e = ctk.CTkEntry(scroll, placeholder_text=placeholder,
                             show="*" if secret else "", height=32)
            e.grid(row=row[0], column=1, columnspan=2,
                   sticky="ew", padx=(0, 8), pady=2)
            self._entries[entry_key] = e
            row[0] += 1

        def token_field(label_key: str, entry_key: str,
                        btn_key: str, btn_cmd) -> None:
            ctk.CTkLabel(scroll, text=i18n.t(label_key) + ":",
                         anchor="e").grid(row=row[0], column=0,
                                          sticky="e", padx=(8, 8), pady=2)
            inner = ctk.CTkFrame(scroll, fg_color="transparent")
            inner.grid(row=row[0], column=1, columnspan=2,
                       sticky="ew", padx=(0, 8), pady=2)
            inner.columnconfigure(0, weight=1)
            e = ctk.CTkEntry(inner, show="*", height=32)
            e.grid(row=0, column=0, sticky="ew")
            ctk.CTkButton(inner, text=i18n.t(btn_key), width=140, height=32,
                          command=btn_cmd).grid(row=0, column=1, padx=(8, 0))
            self._entries[entry_key] = e
            row[0] += 1

        # ---- Crunchyroll ----
        section("settings_section_cr")
        field("settings_etp_rt",    "cr.etp_rt",    "settings_etp_rt_placeholder",    secret=True)
        field("settings_client_id", "cr.client_id", "settings_client_id_placeholder")
        note("settings_cr_note")

        # ---- AniList ----
        section("settings_section_anilist")
        field("settings_client_id", "al.client_id")
        token_field("settings_access_token", "al.access_token",
                    "settings_al_get_token_btn", self._get_anilist_token)
        note("settings_al_note")

        # ---- MyAnimeList ----
        section("settings_section_mal")
        field("settings_client_id", "mal.client_id")

        self._mal_web_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            scroll, text=i18n.t("settings_mal_web_checkbox"),
            variable=self._mal_web_var, command=self._toggle_mal_secret,
        ).grid(row=row[0], column=0, columnspan=3, sticky="w",
               padx=8, pady=(4, 2))
        row[0] += 1

        field("settings_client_secret", "mal.client_secret",
              "settings_client_secret_placeholder", secret=True)

        token_field("settings_access_token", "mal.access_token",
                    "settings_mal_auth_btn", self._get_mal_token)
        note("settings_mal_note")

        # ---- File paths ----
        section("settings_section_paths")
        field("settings_history_path", "store.path", "settings_history_placeholder")
        field("settings_xml_path",     "xml.path",   "settings_xml_placeholder")
        note("settings_paths_note")

        # ---- Interface ----
        section("settings_section_ui")
        ctk.CTkLabel(scroll, text=i18n.t("settings_language") + ":",
                     anchor="e").grid(row=row[0], column=0,
                                      sticky="e", padx=(8, 8), pady=2)

        self._lang_var = ctk.StringVar(
            value=self.app.cfg.get("ui", {}).get("language", "en"))
        lang_menu = ctk.CTkOptionMenu(
            scroll,
            variable=self._lang_var,
            values=i18n.available_langs(),
        )
        lang_menu.grid(row=row[0], column=1, sticky="w", padx=(0, 8), pady=2)
        row[0] += 1
        note("settings_language_note")

        # Tray toggle (applies immediately on save — no restart needed)
        self._tray_var = ctk.BooleanVar(
            value=self.app.cfg.get("ui", {}).get("tray_enabled", False))
        ctk.CTkCheckBox(
            scroll,
            text=i18n.t("settings_tray_enabled"),
            variable=self._tray_var,
        ).grid(row=row[0], column=0, columnspan=3, sticky="w",
               padx=8, pady=(4, 0))
        row[0] += 1
        note("settings_tray_note")

        # ---- Save button ----
        ctk.CTkButton(
            f, text=i18n.t("btn_save"), height=38, command=self._save,
        ).grid(row=1, column=0, sticky="ew", padx=10, pady=10)

        # ---- Version (bottom, unobtrusive, links to the releases page) ----
        self._version_lbl = ctk.CTkLabel(
            f, text=f"v{__version__}",
            font=ctk.CTkFont(size=10),
            text_color=("gray60", "gray50"),
            cursor="hand2",
        )
        self._version_lbl.grid(row=2, column=0, sticky="e", padx=10, pady=(0, 6))
        self._version_lbl.bind("<Button-1>", lambda e: webbrowser.open(RELEASES_URL))

    # ------------------------------------------------------------------ load / save

    def _load_values(self) -> None:
        cfg  = self.app.cfg
        cr   = cfg.get("crunchyroll", {})
        al   = cfg.get("exporters",   {}).get("anilist",  {})
        mal  = cfg.get("exporters",   {}).get("mal",      {})
        xml  = cfg.get("exporters",   {}).get("mal_xml",  {})
        stor = cfg.get("storage",     {})

        def put(key: str, value) -> None:
            e = self._entries.get(key)
            if e and value:
                e.delete(0, "end")
                e.insert(0, str(value))

        put("cr.etp_rt",        cr.get("etp_rt",       ""))
        put("cr.client_id",     cr.get("client_id",    ""))
        put("al.client_id",     al.get("client_id",    ""))
        put("al.access_token",  al.get("access_token", ""))
        put("mal.client_id",     mal.get("client_id",     ""))
        put("mal.client_secret", mal.get("client_secret", ""))
        put("mal.access_token",  mal.get("access_token",  ""))
        put("store.path",       stor.get("path",       ""))
        put("xml.path",         xml.get("path",        ""))

        self._mal_web_var.set(bool(mal.get("client_secret", "")))

    def _save(self) -> None:
        def val(key: str) -> str:
            e = self._entries.get(key)
            return e.get().strip() if e else ""

        cfg = self.app.cfg
        cfg.setdefault("crunchyroll", {})
        cfg["crunchyroll"]["etp_rt"]    = val("cr.etp_rt")
        cfg["crunchyroll"]["client_id"] = val("cr.client_id")

        cfg.setdefault("exporters", {})
        cfg["exporters"].setdefault("anilist", {})
        cfg["exporters"]["anilist"]["client_id"]    = val("al.client_id")
        cfg["exporters"]["anilist"]["access_token"] = val("al.access_token")

        cfg["exporters"].setdefault("mal", {})
        cfg["exporters"]["mal"]["client_id"]     = val("mal.client_id")
        cfg["exporters"]["mal"]["client_secret"] = val("mal.client_secret") if self._mal_web_var.get() else ""
        cfg["exporters"]["mal"]["access_token"]  = val("mal.access_token")

        cfg["exporters"].setdefault("mal_xml", {})
        if val("xml.path"):
            cfg["exporters"]["mal_xml"]["path"] = val("xml.path")

        cfg.setdefault("storage", {})
        if val("store.path"):
            cfg["storage"]["path"] = val("store.path")

        cfg.setdefault("ui", {})
        cfg["ui"]["language"]     = self._lang_var.get()
        cfg["ui"]["tray_enabled"] = self._tray_var.get()

        self.app.save_config()
        self.app.apply_tray_setting()

        # Keep the Sync tab cookie field in sync
        try:
            self.app.tab_fetch._etp_var.set(val("cr.etp_rt"))
        except Exception:
            pass

        from tkinter import messagebox
        messagebox.showinfo(i18n.t("settings_saved_title"),
                            i18n.t("settings_saved_msg"))

    def set_update_available(self, tag: str) -> None:
        """Called from App once the background update check finishes (if a
        newer release was found). Clicking still opens the releases page."""
        self._version_lbl.configure(
            text=i18n.t("settings_update_available", current=__version__, latest=tag),
            text_color=("#b06a00", "#e0a030"),
        )

    def _toggle_mal_secret(self) -> None:
        e = self._entries["mal.client_secret"]
        if self._mal_web_var.get():
            e.configure(state="normal")
        else:
            e.delete(0, "end")
            e.configure(state="disabled")

    # ------------------------------------------------------------------ OAuth

    def _get_anilist_token(self) -> None:
        from tkinter import messagebox, simpledialog

        client_id = self._entries["al.client_id"].get().strip()
        if not client_id:
            messagebox.showerror("Error", i18n.t("oauth_al_no_client_id"))
            return

        try:
            from src.exporters.anilist import AniListExporter
        except ImportError:
            messagebox.showerror("Error", i18n.t("oauth_import_error"))
            return

        webbrowser.open(AniListExporter.get_auth_url(client_id))

        token = simpledialog.askstring(
            i18n.t("oauth_al_dialog_title"),
            i18n.t("oauth_al_prompt"),
            parent=self.frame,
        )
        if token and token.strip():
            e = self._entries["al.access_token"]
            e.delete(0, "end")
            e.insert(0, token.strip())
            messagebox.showinfo(i18n.t("oauth_al_dialog_title"),
                                i18n.t("oauth_al_save_remind"))

    def _get_mal_token(self) -> None:
        from tkinter import messagebox, simpledialog

        client_id = self._entries["mal.client_id"].get().strip()
        if not client_id:
            messagebox.showerror("Error", i18n.t("oauth_mal_no_client_id"))
            return

        try:
            from src.exporters.mal import get_auth_url, exchange_code
        except ImportError:
            messagebox.showerror("Error", i18n.t("oauth_import_error"))
            return

        url, verifier = get_auth_url(client_id)
        webbrowser.open(url)
        messagebox.showinfo(i18n.t("oauth_mal_instructions_title"),
                            i18n.t("oauth_mal_instructions"))

        code = simpledialog.askstring(
            i18n.t("oauth_mal_dialog_title"),
            i18n.t("oauth_mal_prompt"),
            parent=self.frame,
        )
        if not code or not code.strip():
            return

        client_secret = self._entries["mal.client_secret"].get().strip() if self._mal_web_var.get() else ""

        try:
            token = exchange_code(client_id, code.strip(), verifier, client_secret)
            e = self._entries["mal.access_token"]
            e.delete(0, "end")
            e.insert(0, token)
            messagebox.showinfo(i18n.t("oauth_mal_dialog_title"),
                                i18n.t("oauth_mal_save_remind"))
        except Exception as ex:
            messagebox.showerror(i18n.t("oauth_mal_dialog_title"),
                                 i18n.t("oauth_mal_error", error=ex))
