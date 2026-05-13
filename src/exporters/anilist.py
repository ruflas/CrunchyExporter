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

_ID_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    id
    title { romaji english native }
    episodes
    status
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

    def search_anime(self, series_id: str, title: str) -> tuple[dict | None, str | None]:
        for candidate in dict.fromkeys([title, _normalize(title)]):
            try:
                data = self._gql(_SEARCH_QUERY, {"search": candidate})
                media = data.get("Media")
                if media:
                    return media, None
            except ValueError as e:
                return None, str(e)
            except Exception as e:
                return None, str(e)
            time.sleep(0.6)
        return None, "No match found"

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

    def export(self, series: list[SeriesSummary]) -> ExportResult:
        result = ExportResult()
        for s in series:
            media, err = self.search_anime(s.series_id, s.series_title)
            if not media:
                result.failed.append((s.series_title, err or "Not found"))
                continue
            try:
                status = self._determine_status(s, media.get("episodes"))
                variables = {
                    "mediaId": media["id"],
                    "status": status,
                    "progress": s.max_episode,
                }
                if status == "COMPLETED":
                    variables["completedAt"] = self._fuzzy_date(s.last_watched_at)
                self._gql(_UPSERT_MUTATION, variables)
                result.updated.append(s.series_title)
            except Exception as e:
                result.failed.append((s.series_title, str(e)))
            time.sleep(0.6)
        return result
