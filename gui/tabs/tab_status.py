from pathlib import Path
import customtkinter as ctk

from gui import i18n


class StatusTab:
    def __init__(self, frame: ctk.CTkFrame, app) -> None:
        self.app = app
        self.frame = frame
        self._build(frame)
        self.refresh()

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

        for col, text in enumerate([
            i18n.t("library_col_series"),
            i18n.t("library_col_eps"),
            i18n.t("library_col_max"),
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

        store_path = self.app.cfg.get("storage", {}).get("path", "data/history.json")
        store_p = Path(store_path)
        if not store_p.is_absolute():
            store_p = self.app.data_root / store_path

        store     = HistoryStore(store_p)
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
            sorted(summaries, key=lambda x: x.series_title.lower()), start=1
        ):
            row_fg = ("gray90", "gray18") if i % 2 == 0 else ("gray95", "gray22")
            for col, (text, anchor) in enumerate([
                (s.series_title,       "w"),
                (str(s.total_watched), "center"),
                (str(s.max_episode),   "center"),
            ]):
                ctk.CTkLabel(
                    self._list_frame,
                    text=text,
                    anchor=anchor,
                    fg_color=row_fg,
                ).grid(row=i, column=col, sticky="ew", padx=2, pady=1)
