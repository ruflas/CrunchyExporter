import xml.etree.ElementTree as ET
import pytest
from pathlib import Path
from src.exporters.mal_xml import MALXMLExporter
from src.crunchyroll.models import SeriesSummary


def _series(title="Naruto", sid="s1", max_ep=5):
    s = SeriesSummary(series_id=sid, series_title=title)
    s.max_episode = max_ep
    return s


def _export(series, tmp_path):
    out = tmp_path / "animelist.xml"
    result = MALXMLExporter(str(out)).export(series)
    tree = ET.parse(out)
    return tree.getroot(), result


class TestMALXMLExporter:
    def test_required_fields_present(self, tmp_path):
        root, _ = _export([_series()], tmp_path)
        node = root.find("anime")
        assert node.find("series_animedb_id") is not None
        assert node.find("update_on_import") is not None
        assert node.find("my_watched_episodes") is not None

    def test_num_watched_episodes(self, tmp_path):
        root, _ = _export([_series(max_ep=7)], tmp_path)
        assert root.find("anime/my_watched_episodes").text == "7"

    def test_myinfo_present(self, tmp_path):
        root, _ = _export([_series()], tmp_path)
        assert root.find("myinfo") is not None

    def test_title_in_output(self, tmp_path):
        root, _ = _export([_series("Fullmetal Alchemist")], tmp_path)
        assert root.find("anime/series_title").text == "Fullmetal Alchemist"

    def test_special_chars_no_crash(self, tmp_path):
        root, result = _export([_series("Re:Zero − Starting Life in Another World")], tmp_path)
        assert len(result.updated) == 1

    def test_multiple_series_multiple_anime_nodes(self, tmp_path):
        root, _ = _export([_series("A", "s1"), _series("B", "s2"), _series("C", "s3")], tmp_path)
        assert len(root.findall("anime")) == 3

    def test_status_completed_when_max_ep_positive(self, tmp_path):
        root, _ = _export([_series(max_ep=1)], tmp_path)
        assert root.find("anime/my_status").text == "Completed"

    def test_status_plan_to_watch_when_max_ep_zero(self, tmp_path):
        root, _ = _export([_series(max_ep=0)], tmp_path)
        assert root.find("anime/my_status").text == "Plan to Watch"

    def test_export_result_has_all_titles_in_updated(self, tmp_path):
        series = [_series("Naruto", "s1"), _series("Bleach", "s2")]
        _, result = _export(series, tmp_path)
        assert set(result.updated) == {"Naruto", "Bleach"}
        assert len(result.failed) == 0
