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
    # MAL's /anime search rejects long `q` values with 400 "invalid q" —
    # in practice anything much past this returns the same error, and
    # Crunchyroll's English titles (with long subtitles) routinely exceed it.
    _MAX_QUERY_LEN = 64

    @classmethod
    def _title_candidates(cls, title: str) -> list[str]:
        """
        Build a list of query strings to try against MAL's search, from
        most to least specific: the full title first, then the part before
        a subtitle separator (": ", " - ", " — ") if there is one, then a
        hard truncation as a last resort. Long CR titles like
        "Hensuki - Are you willing to fall in love with a pervert, as long
        as she's a cutie?" (83 chars) get rejected outright by MAL, so
        falling back to "Hensuki" is what actually finds the entry.
        """
        candidates = [title]
        for sep in (": ", " - ", " — "):
            if sep in title:
                short = title.split(sep, 1)[0].strip()
                if short and short not in candidates:
                    candidates.append(short)
        if len(title) > cls._MAX_QUERY_LEN:
            truncated = title[:cls._MAX_QUERY_LEN].rsplit(" ", 1)[0].strip()
            if truncated and truncated not in candidates:
                candidates.append(truncated)
        return candidates

    def _search_title(self, title: str) -> dict | None:
        for candidate in self._title_candidates(title):
            resp = self.session.get(
                f"{MAL_API_BASE}/anime",
                params={"q": candidate, "limit": 5, "fields": "id,title,num_episodes,media_type"},
                timeout=10,
            )
            if resp.status_code == 400:
                # "invalid q" — try the next, shorter candidate instead of
                # failing the whole search outright.
                continue
            if not resp.ok:
                try:
                    detail = resp.json()
                except Exception:
                    detail = resp.text
                raise RuntimeError(f"MAL search failed {resp.status_code}: {detail}")
            items = [item["node"] for item in resp.json().get("data", [])]
            if not items:
                continue
            for item in items:
                if item.get("media_type", "").lower() in self._SERIES_TYPES:
                    return item
            return items[0]
        return None

    def _next_sequel(self, anime_id: int) -> dict | None:
        """Follow the 'sequel' relation edge from an anime entry, if any."""
        resp = self.session.get(
            f"{MAL_API_BASE}/anime/{anime_id}",
            params={"fields": "id,title,num_episodes,media_type,related_anime"},
            timeout=10,
        )
        if not resp.ok:
            return None
        for rel in resp.json().get("related_anime", []):
            if rel.get("relation_type") == "sequel":
                return rel.get("node")
        return None

    def search_anime(self, series_id: str, title: str, season_number: int = 1) -> dict | None:
        """
        Crunchyroll rarely puts the season number in the episode title, so a
        plain title search always lands on season 1's MAL entry. When we know
        this is season N (N>1), walk the 'sequel' relation chain from the
        season-1 match to find the entry that actually corresponds to it.
        """
        base = self._search_title(title)
        if not base:
            return None

        anime = base
        hops = max(0, season_number - 1)
        for _ in range(hops):
            nxt = self._next_sequel(anime["id"])
            if not nxt:
                # Couldn't follow the chain far enough — better to fail loudly
                # than silently overwrite the wrong (earlier) season's entry.
                return None
            anime = nxt
        return anime

    def _current_status(self, anime_id: int) -> dict | None:
        resp = self.session.get(
            f"{MAL_API_BASE}/anime/{anime_id}",
            params={"fields": "my_list_status"},
            timeout=10,
        )
        if not resp.ok:
            return None
        return resp.json().get("my_list_status")

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

    def export(self, series: list[SeriesSummary], dry_run: bool = False) -> ExportResult:
        result = ExportResult()
        for s in series:
            try:
                anime = self.search_anime(s.series_id, s.series_title, s.season_number)
                if not anime:
                    result.failed.append((s.series_title, "Not found on MyAnimeList"))
                    continue

                status = self._determine_status(s, anime.get("num_episodes", 0))
                new_progress = s.max_episode
                current = self._current_status(anime["id"])
                old_progress = (current or {}).get("num_episodes_watched", 0)

                # Never let a sync regress progress that's already logged —
                # this is what protects manually-curated or MALSync-imported
                # entries from being overwritten with stale/wrong numbers.
                if current and old_progress >= new_progress:
                    if dry_run:
                        result.planned.append((
                            s.series_id, s.series_title,
                            f"skip — remote progress {old_progress} "
                            f">= Crunchyroll progress {new_progress}",
                            False,
                        ))
                    result.skipped.append(s.series_title)
                    continue

                if dry_run:
                    old_status = (current or {}).get("status", "—")
                    result.planned.append((
                        s.series_id, s.series_title,
                        f"{old_status} {old_progress}ep -> {status} {new_progress}ep",
                        True,
                    ))
                    continue

                self._update_list(anime["id"], status, s)
                result.updated.append(s.series_title)
            except Exception as e:
                result.failed.append((s.series_title, str(e)))
        return result
