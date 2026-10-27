import time
import re
import requests
from src.crunchyroll.models import SeriesSummary
from .base import BaseExporter, ExportResult

ANILIST_URL = "https://graphql.anilist.co"
ANILIST_AUTH_URL = "https://anilist.co/api/v2/oauth/authorize"

# AniList has run degraded at 30 requests/minute for a long time; the real
# limit is read from the X-RateLimit-Limit header after the first request.
_DEFAULT_RATE_LIMIT = 30

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

_VIEWER_QUERY = "query { Viewer { id } }"

_LIST_QUERY = """
query ($userId: Int, $chunk: Int) {
  MediaListCollection(userId: $userId, type: ANIME, chunk: $chunk, perChunk: 500) {
    hasNextChunk
    lists { entries { mediaId status progress } }
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
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        self._interval = 60 / _DEFAULT_RATE_LIMIT
        self._last_request = 0.0
        # Per-run caches: a show's seasons search the same title and walk the
        # same sequel chain (every One Piece arc walks it from the start).
        self._search_cache: dict[str, dict | None] = {}
        self._sequel_cache: dict[int, dict | None] = {}
        self._list: dict[int, dict] | None = None
        self._list_failed = False

    @staticmethod
    def get_auth_url(client_id: str) -> str:
        return f"{ANILIST_AUTH_URL}?client_id={client_id}&response_type=token"

    def _post_once(self, payload: dict) -> requests.Response:
        # Pace requests to stay under the limit: going over gets a 429 with a
        # ~60s penalty, which used to be most of an export's running time.
        wait = self._last_request + self._interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        resp = self.session.post(ANILIST_URL, json=payload, timeout=15)
        self._last_request = time.monotonic()
        limit = resp.headers.get("X-RateLimit-Limit", "")
        if limit.isdigit() and int(limit) > 0:
            self._interval = 60 / int(limit) * 1.05
        return resp

    def _gql(self, query: str, variables: dict) -> dict:
        payload = {"query": query, "variables": variables}
        for attempt in range(3):
            try:
                resp = self._post_once(payload)
            except (requests.ConnectionError, requests.Timeout):
                if attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))
                continue
            if resp.status_code != 429:
                break
            time.sleep(int(resp.headers.get("Retry-After", 60)))
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise ValueError(data["errors"][0]["message"])
        return data["data"]

    def _search_title(self, title: str) -> dict | None:
        if title in self._search_cache:
            return self._search_cache[title]
        failed = False
        for candidate in dict.fromkeys([title, _normalize(title)]):
            try:
                data = self._gql(_SEARCH_QUERY, {"search": candidate})
                media = data.get("Media")
                if media:
                    self._search_cache[title] = media
                    return media
            except Exception:
                failed = True
        if not failed:  # a request error may be temporary: don't remember it
            self._search_cache[title] = None
        return None

    def _next_sequel(self, media_id: int) -> dict | None:
        """Follow the SEQUEL relation edge from an anime entry, if any."""
        if media_id not in self._sequel_cache:
            self._sequel_cache[media_id] = self._fetch_sequel(media_id)
        return self._sequel_cache[media_id]

    def _fetch_sequel(self, media_id: int) -> dict | None:
        data = self._gql(_RELATIONS_QUERY, {"id": media_id})
        media = data.get("Media")
        if not media:
            return None
        for edge in media.get("relations", {}).get("edges", []):
            node = edge.get("node") or {}
            if edge.get("relationType") == "SEQUEL" and node.get("type") == "ANIME":
                return node
        return None

    def search_anime(self, title: str, season_number: int = 1) -> tuple[dict | None, str | None]:
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
        return media, None

    def _load_list(self) -> dict[int, dict]:
        """The user's whole list, {mediaId: {"progress", "status"}}, in one go."""
        user_id = (self._gql(_VIEWER_QUERY, {}).get("Viewer") or {}).get("id")
        if not user_id:
            raise ValueError("AniList didn't return the logged-in user")
        entries: dict[int, dict] = {}
        chunk = 1
        while True:
            col = self._gql(_LIST_QUERY, {"userId": user_id, "chunk": chunk}).get(
                "MediaListCollection") or {}
            for lst in col.get("lists") or []:
                for e in lst.get("entries") or []:
                    entries[e["mediaId"]] = {"progress": e.get("progress") or 0,
                                             "status": e.get("status")}
            if not col.get("hasNextChunk"):
                return entries
            chunk += 1

    def _current_entry(self, media_id: int) -> dict | None:
        # Read the whole list once instead of one request per series; if that
        # fails, fall back to asking for this entry alone.
        if self._list is None and not self._list_failed:
            try:
                self._list = self._load_list()
            except Exception:
                self._list_failed = True
        if self._list is not None:
            return self._list.get(media_id)
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
            media, err = self.search_anime(s.series_title, s.season_number)
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
                            s.series_id, s.series_title,
                            f"skip — remote progress {current.get('progress', 0)} "
                            f">= Crunchyroll progress {new_progress}",
                            False,
                        ))
                    result.skipped.append(s.series_title)
                    continue

                if dry_run:
                    old_progress = current.get("progress", 0) if current else 0
                    old_status = current.get("status", "—") if current else "—"
                    result.planned.append((
                        s.series_id, s.series_title,
                        f"{old_status} {old_progress}ep -> {status} {new_progress}ep",
                        True,
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
                if self._list is not None:
                    self._list[media["id"]] = {"progress": new_progress, "status": status}
                result.updated.append(s.series_title)
            except Exception as e:
                result.failed.append((s.series_title, str(e)))
        return result
