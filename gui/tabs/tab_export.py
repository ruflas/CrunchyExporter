import threading
import webbrowser
from pathlib import Path
import customtkinter as ctk

from gui import i18n
from gui.logbox import LogBox

_GREEN  = "#4caf50"
_ORANGE = "#ff9800"
_GRAY   = "#888888"


class ExportTab:
    def __init__(self, frame: ctk.CTkFrame, app) -> None:
        self.app = app
        self.frame = frame
        self._build(frame)

    # ------------------------------------------------------------------ build

    def _build(self, f: ctk.CTkFrame) -> None:
        f.columnconfigure(0, weight=1)
        f.rowconfigure(1, weight=1)

        # ── Target cards ─────────────────────────────────────────────────────
        cards_frame = ctk.CTkFrame(f, fg_color="transparent")
        cards_frame.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        cards_frame.columnconfigure((0, 1, 2), weight=1)

        self._anilist_var = ctk.BooleanVar(value=True)
        self._mal_var     = ctk.BooleanVar(value=True)
        self._xml_var     = ctk.BooleanVar(value=True)

        self._card_anilist = _TargetCard(
            cards_frame, "AniList",
            checkbox_var=self._anilist_var,
            go_settings_cmd=lambda: self._go_settings(),
        )
        self._card_anilist.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        self._card_mal = _TargetCard(
            cards_frame, "MyAnimeList",
            checkbox_var=self._mal_var,
            go_settings_cmd=lambda: self._go_settings(),
        )
        self._card_mal.grid(row=0, column=1, sticky="nsew", padx=3)

        self._card_xml = _TargetCard(
            cards_frame, i18n.t("export_xml"),
            checkbox_var=self._xml_var,
            go_settings_cmd=None,  # XML never needs setup
        )
        self._card_xml.grid(row=0, column=2, sticky="nsew", padx=(6, 0))

        # ── Bottom: export button + log ───────────────────────────────────────
        bottom = ctk.CTkFrame(f, fg_color="transparent")
        bottom.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 6))
        bottom.columnconfigure(0, weight=1)
        bottom.rowconfigure(1, weight=1)

        btn_row = ctk.CTkFrame(bottom, fg_color="transparent")
        btn_row.grid(row=0, column=0, sticky="w", pady=(0, 8))

        self._export_btn = ctk.CTkButton(
            btn_row, text=i18n.t("export_btn"), width=140,
            command=self._on_export)
        self._export_btn.pack(side="left")

        ctk.CTkLabel(bottom, text=i18n.t("export_progress_label") + ":",
                     anchor="w").grid(row=0, column=0, sticky="e")

        self._log = LogBox(bottom, height=260)
        self._log.grid(row=1, column=0, sticky="nsew", pady=(0, 4))

    # ------------------------------------------------------------------ status refresh

    def refresh_status(self) -> None:
        """Called by App when the Export tab is opened."""
        cfg = self.app.cfg
        exp = cfg.get("exporters", {})

        al_cfg  = exp.get("anilist", {})
        mal_cfg = exp.get("mal",     {})

        # AniList
        if al_cfg.get("access_token", "").strip():
            self._card_anilist.set_status(i18n.t("export_status_ready"), _GREEN, show_setup=False)
        elif al_cfg.get("client_id", "").strip():
            self._card_anilist.set_status(i18n.t("export_status_no_token"), _ORANGE, show_setup=True)
        else:
            self._card_anilist.set_status(i18n.t("export_status_no_id"), _GRAY, show_setup=True)

        # MAL
        if mal_cfg.get("access_token", "").strip():
            self._card_mal.set_status(i18n.t("export_status_ready"), _GREEN, show_setup=False)
        elif mal_cfg.get("client_id", "").strip():
            self._card_mal.set_status(i18n.t("export_status_no_token"), _ORANGE, show_setup=True)
        else:
            self._card_mal.set_status(i18n.t("export_status_no_id"), _GRAY, show_setup=True)

        # XML — always ready
        self._card_xml.set_status(i18n.t("export_status_always"), _GREEN, show_setup=False)

    def _go_settings(self) -> None:
        self.app._nav.set(i18n.t("nav_settings"))
        self.app._show("settings")

    def _set_busy(self, busy: bool) -> None:
        self._export_btn.configure(state="disabled" if busy else "normal")

    # ------------------------------------------------------------------ OAuth flows (main thread)

    def _anilist_auth_flow(self, al_cfg: dict) -> bool:
        from tkinter import messagebox, simpledialog
        client_id = al_cfg.get("client_id", "")
        if not client_id:
            messagebox.showinfo(i18n.t("oauth_al_dialog_title"),
                                i18n.t("oauth_al_no_client_id"))
            return False
        try:
            from src.exporters.anilist import AniListExporter
        except ImportError:
            messagebox.showerror("Error", i18n.t("oauth_import_error"))
            return False

        webbrowser.open(AniListExporter.get_auth_url(client_id))
        token = simpledialog.askstring(
            i18n.t("oauth_al_dialog_title"), i18n.t("oauth_al_prompt"),
            parent=self.frame)
        if not token or not token.strip():
            return False

        token = token.strip()
        self.app.cfg.setdefault("exporters", {}).setdefault("anilist", {})["access_token"] = token
        self.app.save_config()
        self._log.append(i18n.t("oauth_al_saved"), "ok")
        self._sync_entry("al.access_token", token)
        return True

    def _mal_auth_flow(self, mal_cfg: dict) -> bool:
        from tkinter import messagebox, simpledialog
        client_id = mal_cfg.get("client_id", "")
        if not client_id:
            messagebox.showinfo(i18n.t("oauth_mal_dialog_title"),
                                i18n.t("oauth_mal_no_client_id"))
            return False
        try:
            from src.exporters.mal import get_auth_url, exchange_code
        except ImportError:
            messagebox.showerror("Error", i18n.t("oauth_import_error"))
            return False

        url, verifier = get_auth_url(client_id)
        webbrowser.open(url)
        messagebox.showinfo(i18n.t("oauth_mal_instructions_title"),
                            i18n.t("oauth_mal_instructions"))
        code = simpledialog.askstring(
            i18n.t("oauth_mal_dialog_title"), i18n.t("oauth_mal_prompt"),
            parent=self.frame)
        if not code or not code.strip():
            return False
        try:
            token = exchange_code(client_id, code.strip(), verifier,
                                  mal_cfg.get("client_secret", ""))
            self.app.cfg.setdefault("exporters", {}).setdefault("mal", {})["access_token"] = token
            self.app.save_config()
            self._log.append(i18n.t("oauth_mal_saved"), "ok")
            self._sync_entry("mal.access_token", token)
            return True
        except Exception as ex:
            messagebox.showerror(i18n.t("oauth_mal_dialog_title"),
                                 i18n.t("oauth_mal_error", error=ex))
            return False

    def _sync_entry(self, key: str, value: str) -> None:
        try:
            e = self.app.tab_config._entries.get(key)
            if e:
                e.delete(0, "end")
                e.insert(0, value)
        except Exception:
            pass

    # ------------------------------------------------------------------ main action

    def _on_export(self) -> None:
        from tkinter import messagebox

        targets: list[str] = []
        if self._anilist_var.get(): targets.append("anilist")
        if self._mal_var.get():     targets.append("mal")
        if self._xml_var.get():     targets.append("xml")

        if not targets:
            messagebox.showerror("Error", i18n.t("export_err_no_target"))
            return

        if "anilist" in targets:
            al_cfg = self.app.cfg.get("exporters", {}).get("anilist", {})
            if not al_cfg.get("access_token"):
                if not self._anilist_auth_flow(al_cfg):
                    targets.remove("anilist")

        if "mal" in targets:
            mal_cfg = self.app.cfg.get("exporters", {}).get("mal", {})
            if not mal_cfg.get("access_token"):
                if not mal_cfg.get("client_id"):
                    if not messagebox.askyesno(i18n.t("oauth_mal_skip_title"),
                                               i18n.t("oauth_mal_skip_msg")):
                        return
                    targets.remove("mal")
                else:
                    if not self._mal_auth_flow(mal_cfg):
                        targets.remove("mal")

        if not targets:
            return

        self._log.clear()
        self._set_busy(True)

        def log_cb(msg: str, level: str = "info") -> None:
            self.frame.after(0, lambda m=msg, l=level: self._log.append(m, l))

        def on_done(ok: bool) -> None:
            def _finish():
                self._set_busy(False)
                self.refresh_status()
            self.frame.after(0, _finish)

        threading.Thread(
            target=_export_worker,
            args=(targets, self.app.cfg, self.app.data_root, log_cb, on_done),
            daemon=True,
        ).start()


# ------------------------------------------------------------------ TargetCard widget

class _TargetCard(ctk.CTkFrame):
    """Card showing a target's name, checkbox, and configuration status."""

    def __init__(self, master, title: str, checkbox_var: ctk.BooleanVar,
                 go_settings_cmd) -> None:
        super().__init__(master, corner_radius=8)
        self._go_cmd = go_settings_cmd
        self._build(title, checkbox_var)

    def _build(self, title: str, var: ctk.BooleanVar) -> None:
        self.columnconfigure(0, weight=1)

        ctk.CTkCheckBox(
            self, text=title,
            variable=var,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 4))

        self._status_dot = ctk.CTkLabel(
            self, text="●", font=ctk.CTkFont(size=11),
            text_color=_GRAY, width=14)
        self._status_dot.grid(row=1, column=0, sticky="w", padx=(12, 4), pady=(0, 4))

        self._status_lbl = ctk.CTkLabel(
            self, text="—",
            font=ctk.CTkFont(size=11),
            text_color=_GRAY, anchor="w")
        self._status_lbl.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(0, 4))

        self._setup_btn = ctk.CTkButton(
            self, text=i18n.t("export_go_settings"),
            height=26, font=ctk.CTkFont(size=11),
            fg_color=("gray65", "gray35"),
            hover_color=("gray55", "gray28"),
            command=self._go_cmd,
        )
        # Hidden by default; shown when not configured
        self._setup_btn.grid(row=2, column=0, columnspan=2,
                             sticky="ew", padx=10, pady=(0, 10))
        self._setup_btn.grid_remove()

    def set_status(self, text: str, color: str, show_setup: bool) -> None:
        self._status_dot.configure(text_color=color)
        self._status_lbl.configure(text=text, text_color=color)
        if show_setup and self._go_cmd:
            self._setup_btn.grid()
        else:
            self._setup_btn.grid_remove()


# ------------------------------------------------------------------ background worker

def _export_worker(targets, cfg, data_root, log, done):
    try:
        from src.storage.history_store import HistoryStore
        from src.storage.export_log import ExportLog
        from src.exporters.anilist import AniListExporter
        from src.exporters.mal import MALExporter
        from src.exporters.mal_xml import MALXMLExporter
    except ImportError as e:
        log(i18n.t("export_log_import_error", error=e), "error")
        done(False)
        return

    store_path = cfg.get("storage", {}).get("path", "data/history.json")
    store_p = Path(store_path)
    if not store_p.is_absolute():
        store_p = data_root / store_path

    store = HistoryStore(store_p)
    if len(store) == 0:
        log(i18n.t("export_err_no_history"), "warn")
        done(False)
        return

    summaries = store.series_summaries()
    log(i18n.t("export_log_start", count=len(summaries)), "info")

    export_log = ExportLog(data_root / "data" / "export_log.json")

    for target in targets:
        if target == "xml":
            xml_path = cfg.get("exporters", {}).get("mal_xml", {}).get(
                "path", "data/animelist.xml")
            xml_p = Path(xml_path)
            if not xml_p.is_absolute():
                xml_p = data_root / xml_path
            log(i18n.t("export_log_xml_start"), "info")
            try:
                result = MALXMLExporter(str(xml_p)).export(summaries)
                export_log.record("xml", result)
                log(i18n.t("export_log_xml_ok",
                           path=xml_p, count=len(result.updated)), "ok")
            except Exception as e:
                log(i18n.t("export_log_xml_error", error=e), "error")

        elif target == "anilist":
            token = cfg.get("exporters", {}).get("anilist", {}).get("access_token", "")
            if not token:
                log(i18n.t("export_log_no_token", target="AniList"), "warn")
                continue
            log(i18n.t("export_log_anilist_start"), "info")
            try:
                result = AniListExporter(token).export(summaries)
                export_log.record("anilist", result)
                log(i18n.t("export_log_anilist_ok",
                           updated=len(result.updated),
                           skipped=len(result.skipped),
                           failed=len(result.failed)), "ok")
                for title, reason in result.failed:
                    log(i18n.t("export_log_fail_item", title=title, reason=reason), "error")
            except Exception as e:
                log(i18n.t("export_log_anilist_error", error=e), "error")

        elif target == "mal":
            token = cfg.get("exporters", {}).get("mal", {}).get("access_token", "")
            if not token:
                log(i18n.t("export_log_no_token", target="MyAnimeList"), "warn")
                continue
            log(i18n.t("export_log_mal_start"), "info")
            try:
                result = MALExporter(token).export(summaries)
                export_log.record("mal", result)
                log(i18n.t("export_log_mal_ok",
                           updated=len(result.updated),
                           skipped=len(result.skipped),
                           failed=len(result.failed)), "ok")
                for title, reason in result.failed:
                    log(i18n.t("export_log_fail_item", title=title, reason=reason), "error")
            except Exception as e:
                log(i18n.t("export_log_mal_error", error=e), "error")

    log(i18n.t("export_log_done"), "ok")
    done(True)
