import requests
import pytest
from unittest.mock import MagicMock
from src.exporters import mal as mal_module
from src.exporters.mal import MALExporter, get_auth_url
from src.crunchyroll.models import SeriesSummary


def _series(title="Test Anime", sid="s1", ep=5):
    s = SeriesSummary(series_id=sid, series_title=title)
    s.max_episode = ep
    return s


def _ok_resp(items):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"data": [{"node": n} for n in items]}
    return resp


def _err_resp(status=401):
    resp = MagicMock()
    resp.ok = False
    resp.status_code = status
    resp.headers = {}
    resp.raise_for_status.side_effect = requests.HTTPError(f"{status} Client Error")
    return resp


def _patch_resp():
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    return resp


def _status_resp(status=None):
    """Response for the my_list_status lookup export() does before writing."""
    resp = MagicMock()
    resp.ok = True
    resp.json.return_value = {"my_list_status": status} if status else {}
    return resp


def _invalid_q_resp():
    """MAL's response when the search `q` is rejected (e.g. too long)."""
    resp = MagicMock()
    resp.ok = False
    resp.status_code = 400
    resp.json.return_value = {"message": "invalid q", "error": "bad_request"}
    return resp


def _node(anime_id, title, episodes=12, media_type="tv", en="", ja=""):
    return {"id": anime_id, "title": title, "num_episodes": episodes, "media_type": media_type,
            "alternative_titles": {"en": en, "ja": ja, "synonyms": []}}


class FakeAniList:
    """Stands in for AniListExporter.find(): {title: idMal} or an exception."""

    def __init__(self, ids=None, error=None):
        self.ids = ids or {}
        self.error = error
        self.calls = []

    def find(self, title):
        self.calls.append(title)
        if self.error:
            raise self.error
        mal_id = self.ids.get(title)
        return {"id": 999, "idMal": mal_id} if mal_id else None


def _exporter(anilist=None):
    e = MALExporter("fake_token", anilist=anilist or FakeAniList())
    e.session = MagicMock()
    return e


def _routed(e, search, details=None):
    """Answer MAL's search by query and /anime/{id} lookups by id."""
    def get(url, params=None, timeout=None):
        if url.endswith("/anime"):
            return _ok_resp(search.get(params["q"], []))
        if params["fields"] == "my_list_status":
            return _status_resp()
        resp = MagicMock(ok=True, status_code=200)
        resp.json.return_value = (details or {})[int(url.rsplit("/", 1)[1])]
        return resp
    e.session.get.side_effect = get
    e.session.patch.return_value = _patch_resp()
    return e


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(mal_module.time, "sleep", lambda s: None)


class TestMALExportHTTPErrors:
    def test_search_http_error_marks_failed_not_raises(self):
        e = _exporter()
        e.session.get.return_value = _err_resp(401)

        result = e.export([_series("Anime A"), _series("Anime B")])

        assert len(result.updated) == 0
        assert len(result.failed) == 2
        assert result.failed[0][0] == "Anime A"
        assert result.failed[1][0] == "Anime B"

    def test_search_error_on_one_continues_rest(self):
        e = _exporter()
        node = {"id": 1, "title": "Anime B", "num_episodes": 12, "media_type": "tv"}
        # Third response is for the my_list_status check export() does before
        # writing (no current entry -> proceeds with the update normally).
        e.session.get.side_effect = [_err_resp(401), _ok_resp([node]), _status_resp()]
        e.session.patch.return_value = _patch_resp()

        result = e.export([_series("Anime A", "s1"), _series("Anime B", "s2", ep=12)])

        assert len(result.failed) == 1
        assert result.failed[0][0] == "Anime A"
        assert len(result.updated) == 1
        assert result.updated[0] == "Anime B"

    def test_search_not_found_appends_to_failed(self):
        e = _exporter()
        e.session.get.return_value = _ok_resp([])

        result = e.export([_series("Unknown Anime")])

        assert len(result.failed) == 1
        assert "Not found" in result.failed[0][1]
        assert len(result.updated) == 0

    def test_update_list_error_marks_failed(self):
        e = _exporter()
        node = {"id": 1, "title": "Anime A", "num_episodes": 12, "media_type": "tv"}
        e.session.get.return_value = _ok_resp([node])
        patch_resp = MagicMock()
        patch_resp.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
        e.session.patch.return_value = patch_resp

        result = e.export([_series("Anime A", ep=5)])

        assert len(result.failed) == 1
        assert result.failed[0][0] == "Anime A"
        assert len(result.updated) == 0

    def test_successful_export(self):
        e = _exporter()
        node = {"id": 42, "title": "Naruto", "num_episodes": 220, "media_type": "tv"}
        e.session.get.return_value = _ok_resp([node])
        e.session.patch.return_value = _patch_resp()

        result = e.export([_series("Naruto", ep=220)])

        assert len(result.updated) == 1
        assert result.updated[0] == "Naruto"
        assert len(result.failed) == 0

    def test_rate_limit_429_marks_failed_continues(self):
        e = _exporter()
        node = {"id": 1, "title": "B", "num_episodes": 12, "media_type": "tv"}
        e.session.get.side_effect = [_err_resp(429)] * 3 + [_ok_resp([node]), _status_resp()]
        e.session.patch.return_value = _patch_resp()

        result = e.export([_series("A", "s1"), _series("B", "s2", ep=12)])

        assert result.failed[0][0] == "A"
        assert "429" in result.failed[0][1]
        assert result.updated[0] == "B"


class TestRetries:
    NODE = {"id": 1, "title": "Naruto", "num_episodes": 220, "media_type": "tv"}

    def test_timeout_is_retried(self):
        e = _exporter()
        e.session.get.side_effect = [requests.ReadTimeout("slow"), _ok_resp([self.NODE]),
                                     _status_resp()]
        e.session.patch.return_value = _patch_resp()

        assert e.export([_series("Naruto", ep=3)]).updated == ["Naruto"]

    def test_connection_error_is_retried(self):
        e = _exporter()
        e.session.get.side_effect = [requests.ConnectionError("reset"), _ok_resp([self.NODE]),
                                     _status_resp()]
        e.session.patch.return_value = _patch_resp()

        assert e.export([_series("Naruto", ep=3)]).updated == ["Naruto"]

    def test_rate_limit_is_retried(self):
        e = _exporter()
        e.session.get.side_effect = [_err_resp(429), _ok_resp([self.NODE]), _status_resp()]
        e.session.patch.return_value = _patch_resp()

        assert e.export([_series("Naruto", ep=3)]).updated == ["Naruto"]

    def test_gives_up_after_three_timeouts(self):
        e = _exporter()
        e.session.get.side_effect = [requests.ReadTimeout("slow")] * 3

        result = e.export([_series("Naruto", ep=3)])

        assert result.updated == []
        assert result.failed[0][0] == "Naruto"
        assert e.session.get.call_count == 3


class TestSearchMatching:
    """Cases taken from real previews, where MAL's search order was wrong."""

    def test_exact_title_beats_the_first_tv_result(self):
        e = _routed(_exporter(), {"SPY x FAMILY": [
            _node(59027, "Spy x Family Season 3", 13, en="Spy x Family Season 3"),
            _node(50265, "Spy x Family", 12),
        ]})
        assert e._search_title("SPY x FAMILY")["id"] == 50265

    def test_japanese_title_shared_by_the_franchise_does_not_tie(self):
        anilist = FakeAniList()
        e = _routed(_exporter(anilist), {"SPY x FAMILY": [
            _node(59027, "Spy x Family Season 3", 13, en="Spy x Family Season 3",
                  ja="SPY×FAMILY Season 3"),
            _node(50602, "Spy x Family Part 2", 13, ja="SPY×FAMILY"),
            _node(50265, "Spy x Family", 12, ja="SPY×FAMILY"),
        ]})
        assert e._search_title("SPY x FAMILY")["id"] == 50265
        assert anilist.calls == []

    def test_several_exact_titles_are_settled_by_anilist(self):
        anilist = FakeAniList({"Fruits Basket": 38680})
        e = _routed(_exporter(anilist),
                    {"Fruits Basket": [_node(120, "Fruits Basket", 26),
                                       _node(38680, "Fruits Basket (2019)", 25,
                                             en="Fruits Basket")]},
                    {38680: _node(38680, "Fruits Basket (2019)", 25)})
        assert e._search_title("Fruits Basket")["id"] == 38680
        assert anilist.calls == ["Fruits Basket"]

    def test_exact_english_title_of_a_movie_beats_a_tv_result(self):
        e = _routed(_exporter(), {"JUJUTSU KAISEN 0": [
            _node(40748, "Jujutsu Kaisen", 24, en="Jujutsu Kaisen"),
            _node(48561, "Jujutsu Kaisen 0 Movie", 1, "movie", en="Jujutsu Kaisen 0"),
        ]})
        assert e._search_title("JUJUTSU KAISEN 0")["id"] == 48561

    def test_exact_match_does_not_ask_anilist(self):
        anilist = FakeAniList()
        e = _routed(_exporter(anilist), {"Naruto": [_node(20, "Naruto")]})
        e._search_title("Naruto")
        assert anilist.calls == []

    def test_english_title_found_only_through_anilist(self):
        # MAL's search returns nothing for many of Crunchyroll's English titles.
        anilist = FakeAniList({"The Legendary Hero Is Dead!": 51706})
        e = _routed(_exporter(anilist), {},
                    {51706: _node(51706, "Yuusha ga Shinda!", 12)})

        result = e.export([_series("The Legendary Hero Is Dead!", ep=12)])

        assert result.updated == ["The Legendary Hero Is Dead!"]
        assert "/anime/51706/" in e.session.patch.call_args.args[0]

    def test_no_title_match_uses_anilist_mal_id(self):
        anilist = FakeAniList({"Suzume": 50594})
        e = _routed(_exporter(anilist),
                    {"Suzume": [_node(36038, "Net-juu no Susume", 10,
                                      en="Recovery of an MMO Junkie")]},
                    {50594: _node(50594, "Suzume no Tojimari", 1, "movie")})

        result = e.export([_series("Suzume", ep=1)])

        assert result.updated == ["Suzume"]
        assert "/anime/50594/" in e.session.patch.call_args.args[0]

    def test_unrelated_results_and_no_anilist_match_is_not_found(self):
        e = _routed(_exporter(), {"Suzume": [_node(36038, "Net-juu no Susume", 10,
                                                   en="Recovery of an MMO Junkie")]})

        result = e.export([_series("Suzume", ep=1)])

        assert "Not found" in result.failed[0][1]
        e.session.patch.assert_not_called()

    def test_anilist_error_falls_back_to_a_close_title(self):
        e = _routed(_exporter(FakeAniList(error=RuntimeError("AniList down"))),
                    {"Bocchi the Rock": [_node(47917, "Bocchi the Rock!")]})
        assert e._search_title("Bocchi the Rock")["id"] == 47917

    def test_search_is_cached(self):
        e = _routed(_exporter(), {"Naruto": [_node(20, "Naruto")]})
        e._search_title("Naruto")
        e._search_title("Naruto")
        assert e.session.get.call_count == 1


class TestTitleCandidates:
    LONG_TITLE = ("Hensuki - Are you willing to fall in love with a pervert, "
                  "as long as she's a cutie?")

    def test_full_title_tried_first(self):
        assert MALExporter._title_candidates(self.LONG_TITLE)[0] == self.LONG_TITLE

    def test_falls_back_to_part_before_dash(self):
        assert "Hensuki" in MALExporter._title_candidates(self.LONG_TITLE)

    def test_short_title_has_no_fallback(self):
        assert MALExporter._title_candidates("Naruto") == ["Naruto"]

    def test_long_title_without_separator_gets_truncated(self):
        long_title = "A" * 100
        candidates = MALExporter._title_candidates(long_title)
        assert len(candidates[-1]) <= MALExporter._MAX_QUERY_LEN


class TestSearchFallsBackOnInvalidQ:
    def test_long_title_retries_with_short_candidate(self):
        e = _exporter()
        long_title = TestTitleCandidates.LONG_TITLE
        node = {"id": 1, "title": "Hensuki", "num_episodes": 12, "media_type": "tv"}
        e.session.get.side_effect = [_invalid_q_resp(), _ok_resp([node]), _status_resp()]
        e.session.patch.return_value = _patch_resp()

        result = e.export([_series(long_title, ep=2)])

        assert result.updated == [long_title]
        assert result.failed == []
        second_call_params = e.session.get.call_args_list[1].kwargs["params"]
        assert second_call_params["q"] == "Hensuki"

    def test_all_candidates_invalid_q_returns_not_found(self):
        e = _exporter()
        e.session.get.return_value = _invalid_q_resp()

        result = e.export([_series(TestTitleCandidates.LONG_TITLE)])

        assert result.updated == []
        assert "Not found" in result.failed[0][1]


class TestDetermineStatus:
    def _s(self, max_ep):
        s = SeriesSummary(series_id="s1", series_title="X")
        s.max_episode = max_ep
        return s

    def test_completed_exact(self):
        e = MALExporter.__new__(MALExporter)
        assert e._determine_status(self._s(12), 12) == "completed"

    def test_completed_above_total(self):
        e = MALExporter.__new__(MALExporter)
        assert e._determine_status(self._s(13), 12) == "completed"

    def test_watching_below_total(self):
        e = MALExporter.__new__(MALExporter)
        assert e._determine_status(self._s(5), 12) == "watching"

    def test_watching_when_total_zero(self):
        e = MALExporter.__new__(MALExporter)
        assert e._determine_status(self._s(5), 0) == "watching"


class TestMalDate:
    def test_valid_iso_date(self):
        result = MALExporter._mal_date("2024-03-15T10:00:00+00:00")
        assert result == "2024-03-15"

    def test_none_returns_none(self):
        assert MALExporter._mal_date(None) is None

    def test_malformed_returns_none(self):
        assert MALExporter._mal_date("not-a-date") is None

    def test_with_timezone_offset(self):
        result = MALExporter._mal_date("2024-06-01T20:00:00+05:30")
        assert result == "2024-06-01"


class TestGetAuthUrl:
    def test_returns_tuple(self):
        result = get_auth_url("my_client_id")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_url_contains_client_id(self):
        url, _ = get_auth_url("my_client_id")
        assert "my_client_id" in url

    def test_verifier_is_128_chars(self):
        _, verifier = get_auth_url("cid")
        assert len(verifier) == 128

    def test_method_is_plain(self):
        url, _ = get_auth_url("cid")
        assert "plain" in url

    def test_challenge_equals_verifier(self):
        url, verifier = get_auth_url("cid")
        assert verifier in url
