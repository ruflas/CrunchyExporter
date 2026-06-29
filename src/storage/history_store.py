import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from src.crunchyroll.models import Episode, SeriesSummary

DEFAULT_PATH = Path("data") / "history.json"


class HistoryStore:
    def __init__(self, path: Path = DEFAULT_PATH):
        self.path = Path(path)
        self._data: dict = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"last_sync": None, "episodes": []}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def update(self, episodes: list[Episode]) -> int:
        existing_ids = {ep["episode_id"] for ep in self._data["episodes"]}
        new_eps = [ep.to_dict() for ep in episodes if ep.episode_id not in existing_ids]
        self._data["episodes"].extend(new_eps)
        self._data["last_sync"] = datetime.now(timezone.utc).isoformat()
        self.save()
        return len(new_eps)

    def replace(self, episodes: list[Episode]) -> None:
        self._data["episodes"] = [ep.to_dict() for ep in episodes]
        self._data["last_sync"] = datetime.now(timezone.utc).isoformat()
        self.save()

    def all_episodes(self) -> list[Episode]:
        return [Episode.from_dict(ep) for ep in self._data["episodes"]]

    def series_summaries(self, since: Optional[str] = None) -> list[SeriesSummary]:
        """
        since: ISO date/datetime string (e.g. "2026-01-01"). When set, episodes
        watched before this date are excluded — lets users who already track
        older history elsewhere (MALSync, manual entries) only sync what they
        watched on Crunchyroll from that point on. Episodes with no watched_at
        timestamp are kept (can't be filtered reliably).
        """
        summaries: dict[str, SeriesSummary] = {}
        for ep in self.all_episodes():
            if since and ep.watched_at and ep.watched_at < since:
                continue
            if ep.series_id not in summaries:
                summaries[ep.series_id] = SeriesSummary(
                    series_id=ep.series_id,
                    series_title=ep.series_title,
                    season_number=ep.season_number,
                )
            s = summaries[ep.series_id]
            ep_num = int(ep.episode_number)
            if ep_num not in s.episodes_watched:
                s.episodes_watched.append(ep_num)
            if ep_num > s.max_episode:
                s.max_episode = ep_num
            if ep.watched_at:
                if s.last_watched_at is None or ep.watched_at > s.last_watched_at:
                    s.last_watched_at = ep.watched_at
                if s.first_watched_at is None or ep.watched_at < s.first_watched_at:
                    s.first_watched_at = ep.watched_at

        # Movies store episode_number=0 — treat as 1 episode completed
        for s in summaries.values():
            if s.max_episode == 0 and s.total_watched > 0:
                s.max_episode = 1

        # Manual corrections (e.g. from the "My Library" edit dialog) take
        # priority over what was computed from raw Crunchyroll episodes —
        # this is how a wrong season/title/progress gets fixed without
        # touching (or losing) the underlying watch history.
        for series_id, override in self._data.get("overrides", {}).items():
            s = summaries.get(series_id)
            if not s:
                continue
            if override.get("title") is not None:
                s.series_title = override["title"]
            if override.get("season_number") is not None:
                s.season_number = override["season_number"]
            if override.get("max_episode") is not None:
                s.max_episode = override["max_episode"]

        return list(summaries.values())

    def set_override(self, series_id: str, *, title: Optional[str] = None,
                      season_number: Optional[int] = None,
                      max_episode: Optional[int] = None) -> None:
        """Manually pin a series' title/season/progress, overriding whatever
        gets computed from the raw episode history. Used by the GUI's
        "My Library" edit dialog."""
        self._data.setdefault("overrides", {})[series_id] = {
            "title": title,
            "season_number": season_number,
            "max_episode": max_episode,
        }
        self.save()

    def clear_override(self, series_id: str) -> None:
        self._data.get("overrides", {}).pop(series_id, None)
        self.save()

    @property
    def last_sync(self) -> Optional[str]:
        return self._data.get("last_sync")

    def __len__(self) -> int:
        return len(self._data["episodes"])
