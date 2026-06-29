import requests
import pytest
from unittest.mock import MagicMock
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


def _exporter():
    e = MALExporter.__new__(MALExporter)
    e.session = MagicMock()
    return e


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
        e.session.get.side_effect = [_err_resp(429), _ok_resp([node]), _status_resp()]
        e.session.patch.return_value = _patch_resp()

        result = e.export([_series("A", "s1"), _series("B", "s2", ep=12)])

        assert result.failed[0][0] == "A"
        assert result.updated[0] == "B"


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
