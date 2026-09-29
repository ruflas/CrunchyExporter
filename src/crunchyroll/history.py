import requests
from typing import Iterator
from .models import CRToken, Episode

CR_API_HOST = "https://beta-api.crunchyroll.com"
CR_CONTENT_BASE = f"{CR_API_HOST}/content/v2"
PAGE_SIZE = 100


class CRHistoryError(RuntimeError):
    """History download failed; `episodes` holds whatever was fetched before the error."""

    def __init__(self, message: str, episodes: list[Episode]):
        super().__init__(message)
        self.episodes = episodes


class CRHistory:
    def __init__(self, token: CRToken):
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token.access_token}",
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
        })

    def fetch_all(self, locale: str = "en-US") -> list[Episode]:
        episodes = []
        try:
            for ep in self._paginate(locale):
                episodes.append(ep)
        except RuntimeError as e:
            raise CRHistoryError(str(e), episodes) from e
        return episodes

    def _paginate(self, locale: str) -> Iterator[Episode]:
        # The API paginates with an opaque cursor returned in meta.next_page;
        # numeric page values are rejected once the history is long enough (issue #4).
        url = f"{CR_CONTENT_BASE}/{self.token.account_id}/watch-history"
        params = {"page_size": PAGE_SIZE, "locale": locale}
        seen = set()
        while url and url not in seen:
            seen.add(url)
            items, next_page = self._fetch_page(url, params)
            for item in items:
                ep = self._parse_item(item)
                if ep:
                    yield ep
            if not items or not next_page:
                break
            url = next_page if next_page.startswith("http") else f"{CR_API_HOST}{next_page}"
            params = None  # next_page already carries page, page_size and locale

    def _fetch_page(self, url: str, params: dict | None) -> tuple[list[dict], str]:
        resp = self.session.get(url, params=params, timeout=20)
        if not resp.ok:
            raise RuntimeError(f"History fetch failed {resp.status_code}: {resp.text}")
        body = resp.json()
        return body.get("data", []), (body.get("meta") or {}).get("next_page", "")

    def _parse_item(self, item: dict) -> Episode | None:
        panel = item.get("panel", {})
        if not panel:
            return None

        ep_meta = panel.get("episode_metadata", {})

        series_id = ep_meta.get("series_id") or panel.get("id", "")
        series_title = ep_meta.get("series_title") or panel.get("title", "unknown")

        try:
            season_number = int(ep_meta.get("season_number") or 1)
        except (ValueError, TypeError):
            season_number = 1

        try:
            episode_number = float(ep_meta.get("episode_number") or 0)
        except (ValueError, TypeError):
            episode_number = 0.0

        return Episode(
            series_id=series_id,
            series_title=series_title,
            season_number=season_number,
            episode_number=episode_number,
            episode_title=panel.get("title", ""),
            episode_id=panel.get("id", ""),
            watched_at=item.get("date_played"),
            fully_watched=item.get("fully_watched", False),
        )
