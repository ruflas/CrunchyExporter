import json

import pytest
import requests
from src.exporters import anilist as al
from src.exporters.anilist import AniListExporter, _normalize
from src.crunchyroll.models import SeriesSummary


def _exporter():
    return AniListExporter("fake_token")


def _series(title="Naruto", sid="s1", max_ep=5, last_watched=None):
    s = SeriesSummary(series_id=sid, series_title=title)
    s.max_episode = max_ep
    s.last_watched_at = last_watched
    return s


class TestDetermineStatus:
    def test_completed_exact(self):
        e = _exporter()
        s = _series(max_ep=12)
        assert e._determine_status(s, 12) == "COMPLETED"

    def test_completed_above_total(self):
        e = _exporter()
        s = _series(max_ep=13)
        assert e._determine_status(s, 12) == "COMPLETED"

    def test_current_below_total(self):
        e = _exporter()
        s = _series(max_ep=5)
        assert e._determine_status(s, 12) == "CURRENT"

    def test_current_when_total_none(self):
        e = _exporter()
        s = _series(max_ep=5)
        assert e._determine_status(s, None) == "CURRENT"

    def test_current_when_total_zero(self):
        e = _exporter()
        s = _series(max_ep=5)
        assert e._determine_status(s, 0) == "CURRENT"


class TestFuzzyDate:
    def test_valid_iso_date(self):
        result = AniListExporter._fuzzy_date("2024-03-15T10:00:00+00:00")
        assert result == {"year": 2024, "month": 3, "day": 15}

    def test_none_returns_none(self):
        assert AniListExporter._fuzzy_date(None) is None

    def test_malformed_returns_none(self):
        assert AniListExporter._fuzzy_date("not-a-date") is None

    def test_with_timezone_offset(self):
        result = AniListExporter._fuzzy_date("2024-06-01T20:00:00+05:30")
        assert result["year"] == 2024
        assert result["month"] == 6
        assert result["day"] == 1


class TestNormalize:
    def test_collapses_multiple_spaces(self):
        assert _normalize("Dragon  Ball   Z") == "Dragon Ball Z"

    def test_applies_title_case(self):
        assert _normalize("ONE PIECE") == "One Piece"

    def test_strips_leading_trailing_spaces(self):
        assert _normalize("  Naruto  ") == "Naruto"

    def test_single_word(self):
        assert _normalize("BLEACH") == "Bleach"


class FakeResp:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code = status
        self._body = body if body is not None else {}
        self.headers = headers or {}
        self.text = json.dumps(self._body)

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


class FakeAniList:
    """Answers AniList GraphQL calls by query, recording every request."""

    def __init__(self, media=None, sequels=None, user_list=None, fail_first=None):
        self.media = media or {}          # title -> Media
        self.sequels = sequels or {}      # media id -> sequel Media
        self.user_list = user_list or {}  # media id -> (status, progress)
        self.fail_first = list(fail_first or [])  # responses/exceptions to return first
        self.posts = []

    def post(self, url, json=None, timeout=None):
        self.posts.append(json)
        if self.fail_first:
            first = self.fail_first.pop(0)
            if isinstance(first, Exception):
                raise first
            return first
        q, v = json["query"], json["variables"]
        if q is al._VIEWER_QUERY:
            return FakeResp(body={"data": {"Viewer": {"id": 7}}})
        if q is al._LIST_QUERY:
            entries = [{"mediaId": i, "status": st, "progress": pr}
                       for i, (st, pr) in self.user_list.items()]
            return FakeResp(body={"data": {"MediaListCollection": {
                "hasNextChunk": False, "lists": [{"entries": entries}]}}})
        if q is al._SEARCH_QUERY:
            return FakeResp(body={"data": {"Media": self.media.get(v["search"])}})
        if q is al._RELATIONS_QUERY:
            nxt = self.sequels.get(v["id"])
            edges = [{"relationType": "SEQUEL", "node": {**nxt, "type": "ANIME"}}] if nxt else []
            return FakeResp(body={"data": {"Media": {"id": v["id"], "relations": {"edges": edges}}}})
        if q is al._UPSERT_MUTATION:
            return FakeResp(body={"data": {"SaveMediaListEntry": {"id": 1}}})
        raise AssertionError(f"unexpected query {q!r}")

    def count(self, query):
        return sum(1 for p in self.posts if p["query"] is query)


@pytest.fixture
def sleeps(monkeypatch):
    slept = []
    monkeypatch.setattr(al.time, "sleep", slept.append)
    monkeypatch.setattr(al.time, "monotonic", lambda: 1000.0)
    return slept


def _with(fake):
    e = AniListExporter("fake_token")
    e.session = fake
    return e


def _media(media_id, title, episodes=12):
    return {"id": media_id, "title": {"romaji": title}, "episodes": episodes}


class TestRequests:
    def test_user_list_is_read_once_for_all_series(self, sleeps):
        fake = FakeAniList(media={"A": _media(1, "A"), "B": _media(2, "B")},
                           user_list={1: ("CURRENT", 3)})
        e = _with(fake)
        result = e.export([_series("A", "s1", max_ep=5), _series("B", "s2", max_ep=5)], dry_run=True)
        assert fake.count(al._LIST_QUERY) == 1
        assert fake.count(al._ENTRY_QUERY) == 0
        assert [c for _, _, c, _ in result.planned] == ["CURRENT 3ep -> CURRENT 5ep",
                                                       "— 0ep -> CURRENT 5ep"]

    def test_never_regresses_with_the_list_read_once(self, sleeps):
        fake = FakeAniList(media={"A": _media(1, "A")}, user_list={1: ("CURRENT", 8)})
        result = _with(fake).export([_series("A", max_ep=5)])
        assert result.skipped == ["A"]
        assert fake.count(al._UPSERT_MUTATION) == 0

    def test_falls_back_to_one_entry_query_if_the_list_fails(self, sleeps):
        class NoList(FakeAniList):
            def post(self, url, json=None, timeout=None):
                if json["query"] is al._VIEWER_QUERY:
                    self.posts.append(json)
                    return FakeResp(500, {})
                if json["query"] is al._ENTRY_QUERY:
                    self.posts.append(json)
                    return FakeResp(body={"data": {"Media": {"mediaListEntry": {"progress": 9, "status": "CURRENT"}}}})
                return super().post(url, json, timeout)

        fake = NoList(media={"A": _media(1, "A")})
        result = _with(fake).export([_series("A", max_ep=5)], dry_run=True)
        assert result.skipped == ["A"]

    def test_seasons_of_one_show_share_searches_and_sequels(self, sleeps):
        fake = FakeAniList(media={"Show": _media(1, "Show")},
                           sequels={1: _media(2, "Show 2"), 2: _media(3, "Show 3")})
        s2, s3 = _series("Show", "s::2"), _series("Show", "s::3")
        s2.season_number, s3.season_number = 2, 3
        _with(fake).export([_series("Show", "s::1"), s2, s3], dry_run=True)
        assert fake.count(al._SEARCH_QUERY) == 1
        assert fake.count(al._RELATIONS_QUERY) == 2

    def test_no_fixed_pauses_only_pacing(self, sleeps):
        fake = FakeAniList(media={"A": _media(1, "A")})
        _with(fake).export([_series("A", max_ep=5)], dry_run=True)
        assert 0.6 not in sleeps

    def test_pacing_follows_rate_limit_header(self, sleeps):
        fake = FakeAniList(fail_first=[FakeResp(200, {"data": {}}, {"X-RateLimit-Limit": "90"})] * 2)
        e = _with(fake)
        e._gql("query", {})
        e._gql("query", {})
        assert e._interval == pytest.approx(60 / 90 * 1.05)
        assert sleeps[-1] == pytest.approx(e._interval)

    def test_429_is_retried_after_waiting(self, sleeps):
        fake = FakeAniList(fail_first=[FakeResp(429, {}, {"Retry-After": "7"}),
                                       FakeResp(429, {}, {"Retry-After": "7"}),
                                       FakeResp(200, {"data": {"ok": 1}})])
        assert _with(fake)._gql("query", {}) == {"ok": 1}
        assert sleeps.count(7) == 2

    def test_timeout_is_retried(self, sleeps):
        fake = FakeAniList(fail_first=[requests.ReadTimeout("slow"), FakeResp(200, {"data": {"ok": 1}})])
        assert _with(fake)._gql("query", {}) == {"ok": 1}
