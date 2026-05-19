import pytest
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
