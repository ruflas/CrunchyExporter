"""
Status bar — thin strip below the nav bar showing at-a-glance setup state.

Five indicators, left-to-right:
  Cookie   History   AniList   MAL   XML

Green  ●  = ready / configured
Gray   ○  = not set up yet
"""

import json
from pathlib import Path
import customtkinter as ctk

from gui import i18n

_GREEN  = "#4caf50"
_GRAY   = "#666666"


def _dot(ok: bool) -> str:
    return "●" if ok else "○"


class StatusBar(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        kwargs.setdefault("height", 30)
        kwargs.setdefault("corner_radius", 0)
        kwargs.setdefault("fg_color", ("gray78", "gray15"))
        super().__init__(master, **kwargs)
        self.app = app
        self.pack_propagate(False)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(expand=True)

        self._labels: dict[str, ctk.CTkLabel] = {}
        font = ctk.CTkFont(size=11)
        for key in ("cookie", "history", "anilist", "mal", "xml"):
            lbl = ctk.CTkLabel(row, text="", font=font,
                               text_color=_GRAY, padx=12)
            lbl.pack(side="left")
            self._labels[key] = lbl

        # Separator between indicators
        for lbl in list(self._labels.values())[:-1]:
            lbl.configure(text=" ")  # placeholder until first refresh

        self.refresh()

    # ------------------------------------------------------------------ public

    def refresh(self) -> None:
        cfg = self.app.cfg
        pr  = self.app.data_root

        self._update_cookie(cfg)
        self._update_history(cfg, pr)
        self._update_anilist(cfg)
        self._update_mal(cfg)
        self._update_xml()

    # ------------------------------------------------------------------ private

    def _set(self, key: str, ok: bool, text: str) -> None:
        lbl = self._labels[key]
        lbl.configure(
            text=f"{_dot(ok)}  {text}",
            text_color=_GREEN if ok else _GRAY,
        )

    def _update_cookie(self, cfg: dict) -> None:
        ok = bool(cfg.get("crunchyroll", {}).get("etp_rt", "").strip())
        self._set("cookie", ok,
                  i18n.t("status_cookie_ok") if ok else i18n.t("status_cookie_nok"))

    def _update_history(self, cfg: dict, pr: Path) -> None:
        store_path = cfg.get("storage", {}).get("path", "data/history.json")
        store_p = Path(store_path)
        if not store_p.is_absolute():
            store_p = pr / store_path

        ep_count = series_count = 0
        if store_p.exists():
            try:
                data = json.loads(store_p.read_text(encoding="utf-8"))
                episodes = data.get("episodes", [])
                ep_count = len(episodes)
                series_count = len({e.get("series_id") for e in episodes if e.get("series_id")})
            except Exception:
                pass

        ok = ep_count > 0
        text = (i18n.t("status_history_ok", eps=ep_count, series=series_count)
                if ok else i18n.t("status_history_nok"))
        self._set("history", ok, text)

    def _update_anilist(self, cfg: dict) -> None:
        ok = bool(
            cfg.get("exporters", {}).get("anilist", {}).get("access_token", "").strip())
        self._set("anilist", ok,
                  i18n.t("status_anilist_ok") if ok else i18n.t("status_anilist_nok"))

    def _update_mal(self, cfg: dict) -> None:
        ok = bool(
            cfg.get("exporters", {}).get("mal", {}).get("access_token", "").strip())
        self._set("mal", ok,
                  i18n.t("status_mal_ok") if ok else i18n.t("status_mal_nok"))

    def _update_xml(self) -> None:
        # XML export never needs a token
        self._set("xml", True, i18n.t("status_xml_ok"))
