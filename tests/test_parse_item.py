import pytest
from src.crunchyroll.history import CRHistory
from src.crunchyroll.models import CRToken


def _history():
    token = CRToken(access_token="x", refresh_token="y", account_id="acc")
    h = CRHistory.__new__(CRHistory)
    h.token = token
    return h


def _item(series_id="s1", series_title="Naruto", season=1, ep_num=5,
           ep_id="ep1", title="Episode 5", watched=None, fully=False):
    return {
        "panel": {
            "id": ep_id,
            "title": title,
            "episode_metadata": {
                "series_id": series_id,
                "series_title": series_title,
                "season_number": season,
                "episode_number": ep_num,
            },
        },
        "date_played": watched,
        "fully_watched": fully,
    }


class TestParseItem:
    def test_normal_episode(self):
        h = _history()
        ep = h._parse_item(_item())
        assert ep is not None
        assert ep.series_id == "s1"
        assert ep.series_title == "Naruto"
        assert ep.season_number == 1
        assert ep.episode_number == 5.0
        assert ep.episode_id == "ep1"

    def test_empty_panel_returns_none(self):
        h = _history()
        assert h._parse_item({"panel": {}, "date_played": None, "fully_watched": False}) is None

    def test_missing_panel_returns_none(self):
        h = _history()
        assert h._parse_item({"date_played": None, "fully_watched": False}) is None

    def test_movie_empty_episode_metadata(self):
        h = _history()
        item = {
            "panel": {"id": "m1", "title": "A Movie", "episode_metadata": {}},
            "date_played": None,
            "fully_watched": True,
        }
        ep = h._parse_item(item)
        assert ep is not None
        assert ep.episode_number == 0.0

    def test_episode_number_malformed_string(self):
        h = _history()
        item = _item()
        item["panel"]["episode_metadata"]["episode_number"] = "abc"
        ep = h._parse_item(item)
        assert ep.episode_number == 0.0

    def test_episode_number_null(self):
        h = _history()
        item = _item()
        item["panel"]["episode_metadata"]["episode_number"] = None
        ep = h._parse_item(item)
        assert ep.episode_number == 0.0

    def test_season_number_null_defaults_to_one(self):
        h = _history()
        item = _item()
        item["panel"]["episode_metadata"]["season_number"] = None
        ep = h._parse_item(item)
        assert ep.season_number == 1

    def test_fully_watched_false(self):
        h = _history()
        ep = h._parse_item(_item(fully=False))
        assert ep.fully_watched is False
