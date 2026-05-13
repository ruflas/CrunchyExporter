import threading
import webbrowser
from pathlib import Path
import customtkinter as ctk

from gui import i18n
from gui.logbox import LogBox

_CRUNCHYROLL_URL = "https://www.crunchyroll.com"


class FetchTab:
    def __init__(self, frame: ctk.CTkFrame, app) -> None:
        self.app = app
        self.frame = frame
        self._cancelled = False
        self._guide_visible = False
        self._build(frame)

    # ------------------------------------------------------------------ build

    def _build(self, f: ctk.CTkFrame) -> None:
        f.columnconfigure(0, weight=1)
        f.rowconfigure(1, weight=1)

        # ── Steps panel (top, fixed height) ──────────────────────────────────
        steps = ctk.CTkFrame(f, corner_radius=8)
        steps.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        steps.columnconfigure(1, weight=1)

        # Step 1
        self._step_badge(steps, "1", 0)
        s1 = ctk.CTkFrame(steps, fg_color="transparent")
        s1.grid(row=0, column=1, sticky="ew", padx=(0, 14), pady=(10, 4))
        s1.columnconfigure(0, weight=1)

        ctk.CTkLabel(s1, text=i18n.t("sync_step1_title"),
                     font=ctk.CTkFont(size=13, weight="bold"),
                     anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(s1, text=i18n.t("sync_step1_hint"),
                     font=ctk.CTkFont(size=11),
                     text_color=("gray50", "gray60"),
                     anchor="w").grid(row=1, column=0, sticky="w")
        ctk.CTkButton(s1, text=i18n.t("sync_step1_btn"),
                      width=200, height=28,
                      command=lambda: webbrowser.open(_CRUNCHYROLL_URL),
                      ).grid(row=0, column=1, rowspan=2, padx=(10, 0))

        _hsep(steps, 1)

        # Step 2 — collapsible instructions
        self._step_badge(steps, "2", 2)
        s2 = ctk.CTkFrame(steps, fg_color="transparent")
        s2.grid(row=2, column=1, sticky="ew", padx=(0, 14), pady=(10, 4))
        s2.columnconfigure(0, weight=1)

        ctk.CTkLabel(s2, text=i18n.t("sync_step2_title"),
                     font=ctk.CTkFont(size=13, weight="bold"),
                     anchor="w").grid(row=0, column=0, sticky="w")

        self._toggle_btn = ctk.CTkButton(
            s2, text=i18n.t("sync_step2_toggle"),
            width=170, height=26,
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray25"),
            command=self._toggle_guide,
        )
        self._toggle_btn.grid(row=0, column=1, padx=(10, 0))

        self._guide_frame = ctk.CTkFrame(s2, fg_color=("gray88", "gray22"),
                                         corner_radius=6)
        # Hidden initially — revealed by _toggle_guide()
        ctk.CTkLabel(
            self._guide_frame,
            text=i18n.t("sync_step2_guide"),
            font=ctk.CTkFont(family="Consolas", size=11),
            justify="left",
            anchor="w",
        ).pack(padx=12, pady=8, fill="x")

        _hsep(steps, 3)

        # Step 3 — cookie paste
        self._step_badge(steps, "3", 4)
        s3 = ctk.CTkFrame(steps, fg_color="transparent")
        s3.grid(row=4, column=1, sticky="ew", padx=(0, 14), pady=(10, 12))
        s3.columnconfigure(0, weight=1)

        ctk.CTkLabel(s3, text=i18n.t("sync_step3_title"),
                     font=ctk.CTkFont(size=13, weight="bold"),
                     anchor="w").grid(row=0, column=0, columnspan=2, sticky="w",
                                      pady=(0, 4))

        self._etp_var = ctk.StringVar(
            value=self.app.cfg.get("crunchyroll", {}).get("etp_rt", ""))

        self._etp_entry = ctk.CTkEntry(
            s3, textvariable=self._etp_var, show="*", height=34)
        self._etp_entry.grid(row=1, column=0, sticky="ew")

        self._show_btn = ctk.CTkButton(
            s3, text=i18n.t("btn_show"), width=84, height=34,
            command=self._toggle_show)
        self._show_btn.grid(row=1, column=1, padx=(8, 0))

        # ── Bottom bar: options + action buttons ──────────────────────────────
        bottom = ctk.CTkFrame(f, fg_color="transparent")
        bottom.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 6))
        bottom.columnconfigure(0, weight=1)
        bottom.rowconfigure(2, weight=1)

        self._replace_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            bottom, text=i18n.t("sync_replace_check"),
            variable=self._replace_var,
        ).grid(row=0, column=0, sticky="w", pady=(4, 6))

        btn_row = ctk.CTkFrame(bottom, fg_color="transparent")
        btn_row.grid(row=1, column=0, sticky="w", pady=(0, 8))

        self._sync_btn = ctk.CTkButton(
            btn_row, text=i18n.t("sync_btn"), width=150, command=self._on_sync)
        self._sync_btn.pack(side="left")

        self._cancel_btn = ctk.CTkButton(
            btn_row, text=i18n.t("btn_cancel"), width=100,
            fg_color=("gray60", "gray40"),
            hover_color=("gray50", "gray30"),
            state="disabled", command=self._on_cancel)
        self._cancel_btn.pack(side="left", padx=(8, 0))

        ctk.CTkLabel(bottom, text=i18n.t("sync_progress_label") + ":",
                     anchor="w").grid(row=1, column=0, sticky="e")

        self._log = LogBox(bottom, height=180)
        self._log.grid(row=2, column=0, sticky="nsew", pady=(0, 4))

    # ------------------------------------------------------------------ helpers

    def _step_badge(self, parent, number: str, grid_row: int) -> None:
        """Circular number badge for each step."""
        badge = ctk.CTkLabel(
            parent, text=number,
            width=28, height=28,
            corner_radius=14,
            fg_color=("gray30", "gray50"),
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        badge.grid(row=grid_row, column=0, padx=(12, 8), pady=2, sticky="n")

    def _toggle_guide(self) -> None:
        self._guide_visible = not self._guide_visible
        if self._guide_visible:
            self._guide_frame.grid(row=1, column=0, columnspan=2,
                                   sticky="ew", pady=(6, 0))
            self._toggle_btn.configure(text=i18n.t("sync_step2_toggle_close"))
        else:
            self._guide_frame.grid_remove()
            self._toggle_btn.configure(text=i18n.t("sync_step2_toggle"))

    def _toggle_show(self) -> None:
        if self._etp_entry.cget("show") == "*":
            self._etp_entry.configure(show="")
            self._show_btn.configure(text=i18n.t("btn_hide"))
        else:
            self._etp_entry.configure(show="*")
            self._show_btn.configure(text=i18n.t("btn_show"))

    def _set_busy(self, busy: bool) -> None:
        self._sync_btn.configure(state="disabled" if busy else "normal")
        self._cancel_btn.configure(state="normal" if busy else "disabled")

    # ------------------------------------------------------------------ actions

    def _on_cancel(self) -> None:
        self._cancelled = True
        self._log.append(i18n.t("sync_log_cancelled"), "warn")

    def _on_sync(self) -> None:
        etp_rt = self._etp_var.get().strip()
        if not etp_rt:
            from tkinter import messagebox
            messagebox.showerror("Error", i18n.t("sync_err_no_cookie"))
            return

        self._log.clear()
        self._set_busy(True)
        self._cancelled = False

        def log_cb(msg: str, level: str = "info") -> None:
            self.frame.after(0, lambda m=msg, l=level: self._log.append(m, l))

        def on_done(ok: bool) -> None:
            def _finish():
                self._set_busy(False)
                if ok:
                    self.app.tab_status.refresh()
                    self.app.refresh_status()
            self.frame.after(0, _finish)

        threading.Thread(
            target=_sync_worker,
            args=(
                etp_rt,
                self._replace_var.get(),
                self.app.cfg,
                self.app.data_root,
                log_cb,
                on_done,
                lambda: self._cancelled,
            ),
            daemon=True,
        ).start()


# ------------------------------------------------------------------ helpers

def _hsep(parent, grid_row: int) -> None:
    """Thin horizontal separator between steps."""
    ctk.CTkFrame(parent, height=1, fg_color=("gray70", "gray30"),
                 corner_radius=0).grid(
        row=grid_row, column=0, columnspan=2, sticky="ew",
        padx=12, pady=0)


# ------------------------------------------------------------------ background worker

def _sync_worker(etp_rt, replace, cfg, data_root, log, done, is_cancelled):
    try:
        from src.crunchyroll.auth import (
            CRAuth, CRAuthError, DEFAULT_CLIENT_ID, DEFAULT_CLIENT_SECRET)
        from src.crunchyroll.history import CRHistory, PAGE_SIZE
        from src.storage.history_store import HistoryStore
    except ImportError as e:
        log(i18n.t("sync_log_import_error", error=e), "error")
        log(i18n.t("sync_log_expected_path", path=project_root / "src"), "error")
        done(False)
        return

    cr_cfg     = cfg.get("crunchyroll", {})
    store_path = cfg.get("storage", {}).get("path", "data/history.json")
    locale     = cfg.get("locale", "en-US")

    store_p = Path(store_path)
    if not store_p.is_absolute():
        store_p = data_root / store_path

    log(i18n.t("sync_log_logging_in"), "info")
    try:
        auth  = CRAuth(
            client_id=cr_cfg.get("client_id") or DEFAULT_CLIENT_ID,
            client_secret=cr_cfg.get("client_secret") or DEFAULT_CLIENT_SECRET,
        )
        token = auth.login_with_etp_rt(etp_rt)
    except Exception as e:
        log(i18n.t("sync_log_auth_error", error=e), "error")
        done(False)
        return

    log(i18n.t("sync_log_logged_in", account_id=token.account_id), "ok")
    log(i18n.t("sync_log_downloading"), "info")

    try:
        cr       = CRHistory(token)
        episodes = []
        for ep in cr._paginate(locale):
            if is_cancelled():
                log(i18n.t("sync_log_cancelled"), "warn")
                done(False)
                return
            episodes.append(ep)
            if len(episodes) % PAGE_SIZE == 0:
                log(i18n.t("sync_log_page", count=len(episodes)), "info")
        log(i18n.t("sync_log_dl_done", count=len(episodes)), "ok")
    except Exception as e:
        log(i18n.t("sync_log_history_error", error=e), "error")
        done(False)
        return

    store = HistoryStore(store_p)
    if replace:
        store.replace(episodes)
        log(i18n.t("sync_log_replaced", count=len(episodes), path=store_p), "ok")
    else:
        added = store.update(episodes)
        log(i18n.t("sync_log_added",  added=added), "ok")
        log(i18n.t("sync_log_total",
                   total=len(store),
                   series=len(store.series_summaries())), "ok")

    done(True)
