import pytest
from src.crunchyroll.history import CRHistory, CRHistoryError, CR_API_HOST, PAGE_SIZE
from src.crunchyroll.models import CRToken


class FakeResponse:
    def __init__(self, status: int, body: dict):
        self.status_code = status
        self.ok = status < 400
        self._body = body
        self.text = str(body)

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, responses: list[FakeResponse]):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return self.responses.pop(0)


def make_item(n: int) -> dict:
    return {
        "date_played": "2026-01-01T00:00:00Z",
        "fully_watched": True,
        "panel": {
            "id": f"EP{n}",
            "title": f"Episode {n}",
            "episode_metadata": {"series_id": "S1", "series_title": "My Anime", "episode_number": n},
        },
    }


def page(start: int, count: int, next_page: str = "") -> FakeResponse:
    return FakeResponse(200, {
        "total": count,
        "data": [make_item(i) for i in range(start, start + count)],
        "meta": {"next_page": next_page, "prev_page": ""},
    })


def make_history(responses: list[FakeResponse]) -> CRHistory:
    h = object.__new__(CRHistory)
    h.token = CRToken(access_token="x", refresh_token="y", account_id="123")
    h.session = FakeSession(responses)
    return h


def test_follows_next_page_cursor():
    h = make_history([
        page(0, 2, "/content/v2/123/watch-history?page=CURSOR1&page_size=100"),
        page(2, 2, "/content/v2/123/watch-history?page=CURSOR2&page_size=100"),
        page(4, 1),
    ])
    episodes = h.fetch_all()
    assert [e.episode_id for e in episodes] == ["EP0", "EP1", "EP2", "EP3", "EP4"]
    calls = h.session.calls
    assert calls[0][1] == {"page_size": PAGE_SIZE, "locale": "en-US"}
    assert calls[1] == (f"{CR_API_HOST}/content/v2/123/watch-history?page=CURSOR1&page_size=100", None)
    assert calls[2][0].endswith("page=CURSOR2&page_size=100")


def test_never_sends_numeric_page():
    h = make_history([page(0, PAGE_SIZE, "/next?page=C1"), page(0, 3)])
    h.fetch_all()
    for url, params in h.session.calls:
        assert "page" not in (params or {})


def test_stops_on_empty_next_page_even_if_page_full():
    h = make_history([page(0, PAGE_SIZE)])
    assert len(h.fetch_all()) == PAGE_SIZE
    assert len(h.session.calls) == 1


def test_stops_on_empty_data():
    h = make_history([page(0, 0, "/next?page=C1")])
    assert h.fetch_all() == []
    assert len(h.session.calls) == 1


def test_stops_on_repeated_cursor():
    h = make_history([page(0, 1, "/next?page=SAME"), page(1, 1, "/next?page=SAME")])
    assert len(h.fetch_all()) == 2
    assert len(h.session.calls) == 2


def test_error_mid_pagination_keeps_partial_episodes():
    error = FakeResponse(400, {"code": "content.get_watch_history_v2.format_validation_error"})
    h = make_history([page(0, 3, "/next?page=C1"), error])
    with pytest.raises(CRHistoryError) as exc:
        h.fetch_all()
    assert "400" in str(exc.value)
    assert [e.episode_id for e in exc.value.episodes] == ["EP0", "EP1", "EP2"]
