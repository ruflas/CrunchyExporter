import time
import re
import requests
from src.crunchyroll.models import SeriesSummary
from .base import BaseExporter, ExportResult

ANILIST_URL = "https://graphql.anilist.co"
ANILIST_AUTH_URL = "https://anilist.co/api/v2/oauth/authorize"

_SEARCH_QUERY = """
query ($search: String) {
  Media(search: $search, type: ANIME) {
    id
    title { romaji english native }
    episodes
    status
  }
}
"""

_RELATIONS_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    id
    title { romaji english native }
    episodes
    status
    relations {
      edges {
        relationType
        node { id type title { romaji english native } episodes status }
      }
    }
  }
}
"""

_ENTRY_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    mediaListEntry { progress status }
  }
}
"""

_UPSERT_MUTATION = """
mutation ($mediaId: Int, $status: MediaListStatus, $progress: Int, $completedAt: FuzzyDateInput) {
  SaveMediaListEntry(mediaId: $mediaId, status: $status, progress: $progress, completedAt: $completedAt) {
    id
    status
    progress
    completedAt { year month day }
  }
}
"""


def _normalize(title: str) -> str:
    """Lowercase and collapse whitespace — helps match CR all-caps titles."""
    return re.sub(r"\s+", " ", title).strip().title()


class AniListExporter(BaseExporter):
    def __init__(self, access_token: str):
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @staticmethod
    def get_auth_url(client_id: str) -> str:
        return f"{ANILIST_AUTH_URL}?client_id={client_id}&response_type=token"

    def _gql(self, query: str, variables: dict) -> dict:
        resp = requests.post(
            ANILIST_URL,
            json={"query": query, "variables": variables},
            headers=self.headers,
            timeout=15,
        )
        # AniList rate limit: wait and retry once
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 60))
            time.sleep(retry_after)
            resp = requests.post(
                ANILIST_URL,
                json={"query": query, "variables": variables},
                headers=self.headers,
                timeout=15,
            )
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise ValueError(data["errors"][0]["message"])
        return data["data"]

    def _search_title(self, title: str) -> dict | None:
        for candidate in dict.fromkeys([title, _normalize(title)]):
            try:
                data = self._gql(_SEARCH_QUERY, {"search": candidate})
                media = data.get("Media")
                if media:
                    return media
            except Exception:
                pass
            time.sleep(0.6)
        return None

    def _next_sequel(self, media_id: int) -> dict | None:
        """Follow the SEQUEL relation edge from an anime entry, if any."""
        data = self._gql(_RELATIONS_QUERY, {"id": media_id})
        media = data.get("Media")
        if not media:
            return None
        for edge in media.get("relations", {}).get("edges", []):
            node = edge.get("node") or {}
            if edge.get("relationType") == "SEQUEL" and node.get("type") == "ANIME":
                return node
        return None

    def search_anime(self, series_id: str, title: str, season_number: int = 1) -> tuple[dict | None, str | None]:
        """
        Crunchyroll rarely puts the season number in the episode title, so a
        plain title search always lands on season 1's AniList entry. When we
        know this is season N (N>1), walk the SEQUEL relation chain from the
        season-1 match to find the entry that actually corresponds to it.
        """
        base = self._search_title(title)
        if not base:
            return None, "No match found"

        media = base
        hops = max(0, season_number - 1)
        for _ in range(hops):
            nxt = self._next_sequel(media["id"])
            if not nxt:
                # Couldn't follow the chain far enough — better to fail loudly
                # than silently overwrite the wrong (earlier) season's entry.
                return None, (
                    f"Season {season_number} requested but no sequel found "
                    f"after '{media.get('title', {}).get('romaji', title)}'"
                )
            media = nxt
            time.sleep(0.6)
        return media, None

    def _current_entry(self, media_id: int) -> dict | None:
        try:
            data = self._gql(_ENTRY_QUERY, {"id": media_id})
            return (data.get("Media") or {}).get("mediaListEntry")
        except Exception:
            return None

    def _determine_status(self, series: SeriesSummary, total_episodes: int | None) -> str:
        if total_episodes and series.max_episode >= total_episodes:
            return "COMPLETED"
        return "CURRENT"

    @staticmethod
    def _fuzzy_date(iso: str | None) -> dict | None:
        if not iso:
            return None
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            return {"year": dt.year, "month": dt.month, "day": dt.day}
        except Exception:
            return None

    def export(self, series: list[SeriesSummary], dry_run: bool = False) -> ExportResult:
        result = ExportResult()
        for s in series:
            media, err = self.search_anime(s.series_id, s.series_title, s.season_number)
            if not media:
                result.failed.append((s.series_title, err or "Not found"))
                continue
            try:
                status = self._determine_status(s, media.get("episodes"))
                new_progress = s.max_episode
                current = self._current_entry(media["id"])

                # Never let a sync regress progress that's already logged —
                # this is what protects manually-curated or MALSync-imported
                # entries from being overwritten with stale/wrong numbers.
                if current and current.get("progress", 0) >= new_progress:
                    if dry_run:
                        result.planned.append((
                            s.series_title,
                            f"skip — remote progress {current.get('progress', 0)} "
                            f">= Crunchyroll progress {new_progress}",
                        ))
                    result.skipped.append(s.series_title)
                    continue

                if dry_run:
                    old_progress = current.get("progress", 0) if current else 0
                    old_status = current.get("status", "—") if current else "—"
                    result.planned.append((
                        s.series_title,
                        f"{old_status} {old_progress}ep -> {status} {new_progress}ep",
                    ))
                    continue

                variables = {
                    "mediaId": media["id"],
                    "status": status,
                    "progress": new_progress,
                }
                if status == "COMPLETED":
                    variables["completedAt"] = self._fuzzy_date(s.last_watched_at)
                self._gql(_UPSERT_MUTATION, variables)
                result.updated.append(s.series_title)
            except Exception as e:
                result.failed.append((s.series_title, str(e)))
            time.sleep(0.6)
        return result
