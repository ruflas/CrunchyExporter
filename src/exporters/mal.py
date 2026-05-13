import secrets
import requests
from urllib.parse import urlencode
from src.crunchyroll.models import SeriesSummary
from .base import BaseExporter, ExportResult

MAL_API_BASE = "https://api.myanimelist.net/v2"
MAL_AUTH_URL = "https://myanimelist.net/v1/oauth2/authorize"
MAL_TOKEN_URL = "https://myanimelist.net/v1/oauth2/token"


def get_auth_url(client_id: str) -> tuple[str, str]:
    """Returns (auth_url, code_verifier). MAL uses PKCE plain — challenge == verifier."""
    verifier = secrets.token_urlsafe(96)[:128]
    params = urlencode({
        "response_type": "code",
        "client_id": client_id,
        "code_challenge": verifier,
        "code_challenge_method": "plain",
    })
    return f"{MAL_AUTH_URL}?{params}", verifier


def exchange_code(client_id: str, code: str, verifier: str, client_secret: str = "") -> str:
    """Exchange auth code for access token. Returns the access_token."""
    data = {
        "client_id": client_id,
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": verifier,
    }
    if client_secret:
        data["client_secret"] = client_secret
    resp = requests.post(MAL_TOKEN_URL, data=data, timeout=15)
    if not resp.ok:
        raise RuntimeError(f"Token exchange failed {resp.status_code}: {resp.text}")
    return resp.json()["access_token"]


class MALExporter(BaseExporter):
    def __init__(self, access_token: str):
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {access_token}"})

    _SERIES_TYPES = {"tv", "ona", "ova"}

    def search_anime(self, series_id: str, title: str) -> dict | None:
        resp = self.session.get(
            f"{MAL_API_BASE}/anime",
            params={"q": title, "limit": 5, "fields": "id,title,num_episodes,media_type"},
            timeout=10,
        )
        resp.raise_for_status()
        items = [item["node"] for item in resp.json().get("data", [])]
        if not items:
            return None
        for item in items:
            if item.get("media_type", "").lower() in self._SERIES_TYPES:
                return item
        return items[0]

    def _determine_status(self, series: SeriesSummary, total_episodes: int) -> str:
        if total_episodes and series.max_episode >= total_episodes:
            return "completed"
        return "watching"

    @staticmethod
    def _mal_date(iso: str | None) -> str | None:
        if not iso:
            return None
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return None

    def _update_list(self, anime_id: int, status: str, series: SeriesSummary) -> None:
        data: dict = {
            "status": status,
            "num_watched_episodes": series.max_episode,
        }
        start = self._mal_date(series.first_watched_at)
        if start:
            data["start_date"] = start
        if status == "completed":
            finish = self._mal_date(series.last_watched_at)
            if finish:
                data["finish_date"] = finish
        self.session.patch(
            f"{MAL_API_BASE}/anime/{anime_id}/my_list_status",
            data=data,
            timeout=10,
        ).raise_for_status()

    def export(self, series: list[SeriesSummary]) -> ExportResult:
        result = ExportResult()
        for s in series:
            anime = self.search_anime(s.series_id, s.series_title)
            if not anime:
                result.failed.append((s.series_title, "Not found on MyAnimeList"))
                continue
            try:
                status = self._determine_status(s, anime.get("num_episodes", 0))
                self._update_list(anime["id"], status, s)
                result.updated.append(s.series_title)
            except Exception as e:
                result.failed.append((s.series_title, str(e)))
        return result
