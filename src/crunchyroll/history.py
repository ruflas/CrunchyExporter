import requests
from typing import Iterator
from .models import CRToken, Episode

CR_CONTENT_BASE = "https://beta-api.crunchyroll.com/content/v2"
PAGE_SIZE = 100


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
        for ep in self._paginate(locale):
            episodes.append(ep)
        return episodes

    def _paginate(self, locale: str) -> Iterator[Episode]:
        page = 1
        while True:
            items = self._fetch_page(page, locale)
            if not items:
                break
            for item in items:
                ep = self._parse_item(item)
                if ep:
                    yield ep
            if len(items) < PAGE_SIZE:
                break
            page += 1

    def _fetch_page(self, page: int, locale: str) -> list[dict]:
        url = f"{CR_CONTENT_BASE}/{self.token.account_id}/watch-history"
        resp = self.session.get(
            url,
            params={
                "page_size": PAGE_SIZE,
                "page": page,
                "locale": locale,
            },
            timeout=20,
        )
        if not resp.ok:
            raise RuntimeError(f"History fetch failed {resp.status_code}: {resp.text}")
        return resp.json().get("data", [])

    def _parse_item(self, item: dict) -> Episode | None:
        panel = item.get("panel", {})
        if not panel:
            return None

        ep_meta = panel.get("episode_metadata", {})
        series_meta = ep_meta if ep_meta else panel

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
