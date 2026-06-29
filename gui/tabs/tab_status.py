from pathlib import Path
import customtkinter as ctk

from gui import i18n


class StatusTab:
    def __init__(self, frame: ctk.CTkFrame, app) -> None:
        self.app = app
        self.frame = frame
        self._build(frame)
        self.refresh()

    # ------------------------------------------------------------------ store helper

    def _store_path(self) -> Path:
        store_path = self.app.cfg.get("storage", {}).get("path", "data/history.json")
        p = Path(store_path)
        return p if p.is_absolute() else self.app.data_root / store_path

    # ------------------------------------------------------------------ build

    def _build(self, f: ctk.CTkFrame) -> None:
        f.columnconfigure(0, weight=1)
        f.rowconfigure(2, weight=1)

        # Top bar: last sync info + refresh button
        top = ctk.CTkFrame(f, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))
        top.columnconfigure(0, weight=1)

        self._sync_label = ctk.CTkLabel(
            top,
            text=i18n.t("library_last_sync", time=i18n.t("library_never")),
            font=ctk.CTkFont(size=12),
        )
        self._sync_label.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            top, text=i18n.t("btn_refresh"), width=110, command=self.refresh,
        ).grid(row=0, column=1, sticky="e")

        # Summary line
        self._summary_label = ctk.CTkLabel(
            f, text="",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray60"),
        )
        self._summary_label.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 4))

        # Scrollable table
        self._list_frame = ctk.CTkScrollableFrame(f)
        self._list_frame.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self._list_frame.columnconfigure(0, weight=3)
        self._list_frame.columnconfigure(1, weight=1)
        self._list_frame.columnconfigure(2, weight=1)
        self._list_frame.columnconfigure(3, weight=0)

        for col, text in enumerate([
            i18n.t("library_col_series"),
            i18n.t("library_col_eps"),
            i18n.t("library_col_max"),
            "",
        ]):
            ctk.CTkLabel(
                self._list_frame, text=text,
                font=ctk.CTkFont(weight="bold"),
            ).grid(row=0, column=col, sticky="ew", padx=4, pady=(0, 6))

    # ------------------------------------------------------------------ refresh

    def refresh(self) -> None:
        try:
            from src.storage.history_store import HistoryStore
        except ImportError:
            self._sync_label.configure(text=i18n.t("library_import_error"))
            return

        store     = HistoryStore(self._store_path())
        summaries = store.series_summaries()

        sync_time = store.last_sync or i18n.t("library_never")
        self._sync_label.configure(
            text=i18n.t("library_last_sync", time=sync_time))
        self._summary_label.configure(
            text=i18n.t("library_summary",
                        series=len(summaries), episodes=len(store)))

        # Remove old data rows, keeping the header at row 0
        for widget in self._list_frame.winfo_children():
            info = widget.grid_info()
            if info and int(info.get("row", 0)) > 0:
                widget.destroy()

        if not summaries:
            ctk.CTkLabel(
                self._list_frame,
                text=i18n.t("library_empty"),
                text_color=("gray50", "gray60"),
            ).grid(row=1, column=0, columnspan=3, pady=16)
            return

        for i, s in enumerate(
            sorted(summaries, key=lambda x: (x.series_title.lower(), x.season_number)),
            start=1,
        ):
            row_fg = ("gray90", "gray18") if i % 2 == 0 else ("gray95", "gray22")
            # Crunchyroll reuses the same series_id (and title) across
            # seasons — show the season number so same-title rows are
            # distinguishable instead of looking like duplicates.
            display_title = (
                s.series_title if s.season_number <= 1
                else i18n.t("library_season_suffix", title=s.series_title, season=s.season_number)
            )
            for col, (text, anchor) in enumerate([
                (display_title,        "w"),
                (str(s.total_watched), "center"),
                (str(s.max_episode),   "center"),
            ]):
                ctk.CTkLabel(
                    self._list_frame,
                    text=text,
                    anchor=anchor,
                    fg_color=row_fg,
                ).grid(row=i, column=col, sticky="ew", padx=2, pady=1)

            ctk.CTkButton(
                self._list_frame, text="✎", width=28, fg_color=row_fg,
                hover_color=("gray80", "gray28"), text_color=("gray10", "gray90"),
                command=lambda s=s: self._open_edit(s),
            ).grid(row=i, column=3, sticky="ew", padx=2, pady=1)

    # ------------------------------------------------------------------ edit

    def _open_edit(self, summary) -> None:
        _EditSeriesDialog(self.frame, summary, on_save=self._save_override)

    def _save_override(self, series_id: str, title: str, season_number: int, max_episode: int) -> None:
        from src.storage.history_store import HistoryStore
        store = HistoryStore(self._store_path())
        store.set_override(series_id, title=title, season_number=season_number, max_episode=max_episode)
        self.refresh()


# ------------------------------------------------------------------ edit dialog

class _EditSeriesDialog(ctk.CTkToplevel):
    """Small standalone window to manually correct a series' title, season
    number or progress. Saving writes a per-series override into
    history.json (the raw watch history is never modified); cancelling /
    closing the window applies nothing."""

    def __init__(self, master, summary, on_save) -> None:
        super().__init__(master)
        self.title(i18n.t("library_edit_title"))
        self.geometry("380x280")
        self.resizable(False, False)
        self._on_save = on_save
        self._series_id = summary.series_id
        self.columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text=i18n.t("library_edit_field_title")).grid(
            row=0, column=0, sticky="w", padx=(16, 8), pady=(20, 6))
        self._title_entry = ctk.CTkEntry(self)
        self._title_entry.insert(0, summary.series_title)
        self._title_entry.grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=(20, 6))

        ctk.CTkLabel(self, text=i18n.t("library_edit_field_season")).grid(
            row=1, column=0, sticky="w", padx=(16, 8), pady=6)
        self._season_entry = ctk.CTkEntry(self)
        self._season_entry.insert(0, str(summary.season_number))
        self._season_entry.grid(row=1, column=1, sticky="ew", padx=(0, 16), pady=6)

        ctk.CTkLabel(self, text=i18n.t("library_edit_field_progress")).grid(
            row=2, column=0, sticky="w", padx=(16, 8), pady=6)
        self._progress_entry = ctk.CTkEntry(self)
        self._progress_entry.insert(0, str(summary.max_episode))
        self._progress_entry.grid(row=2, column=1, sticky="ew", padx=(0, 16), pady=6)

        self._error_lbl = ctk.CTkLabel(self, text="", text_color="#e05555", anchor="w")
        self._error_lbl.grid(row=3, column=0, columnspan=2, sticky="ew", padx=16)

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=4, column=0, columnspan=2, pady=20)
        ctk.CTkButton(
            btns, text=i18n.t("library_edit_save"), width=120, command=self._save,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btns, text=i18n.t("library_edit_cancel"), width=120,
            fg_color=("gray65", "gray35"), hover_color=("gray55", "gray28"),
            command=self.destroy,
        ).pack(side="left")

        self.transient(master)
        self.grab_set()
        self._title_entry.focus_set()

    def _save(self) -> None:
        title = self._title_entry.get().strip()
        if not title:
            self._error_lbl.configure(text=i18n.t("library_edit_err_title"))
            return
        try:
            season = int(self._season_entry.get().strip())
            progress = int(self._progress_entry.get().strip())
            if season < 1 or progress < 0:
                raise ValueError
        except ValueError:
            self._error_lbl.configure(text=i18n.t("library_edit_err_numbers"))
            return

        self._on_save(self._series_id, title, season, progress)
        self.destroy()
