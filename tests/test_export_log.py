import json
import pytest
from src.exporters.base import ExportResult
from src.storage.export_log import ExportLog


def _result(updated=None, skipped=None, failed=None):
    r = ExportResult()
    r.updated = updated or []
    r.skipped = skipped or []
    r.failed = failed or []
    return r


class TestExportLog:
    def test_record_creates_file(self, tmp_path):
        log = ExportLog(tmp_path / "export_log.json")
        log.record("anilist", _result(updated=["Naruto", "Bleach"],
                                      failed=[("One Piece", "not found")]))

        assert log.path.exists()
        data = json.loads(log.path.read_text())
        assert "last_export" in data
        t = data["targets"]["anilist"]
        assert t["updated"] == 2
        assert t["skipped"] == 0
        assert t["failed"] == [["One Piece", "not found"]]

    def test_record_multiple_targets(self, tmp_path):
        log = ExportLog(tmp_path / "export_log.json")
        log.record("anilist", _result(updated=["A"]))
        log.record("mal", _result(updated=["A", "B"], failed=[("C", "err")]))

        assert log.get_target("anilist")["updated"] == 1
        assert log.get_target("mal")["updated"] == 2
        assert log.get_target("mal")["failed"] == [["C", "err"]]

    def test_record_overwrites_same_target(self, tmp_path):
        log = ExportLog(tmp_path / "export_log.json")
        log.record("anilist", _result(updated=["A"]))
        log.record("anilist", _result(updated=["A", "B"]))

        assert log.get_target("anilist")["updated"] == 2

    def test_get_target_missing_returns_none(self, tmp_path):
        log = ExportLog(tmp_path / "export_log.json")
        assert log.get_target("xml") is None

    def test_last_export_none_when_empty(self, tmp_path):
        log = ExportLog(tmp_path / "export_log.json")
        assert log.last_export is None

    def test_last_export_set_after_record(self, tmp_path):
        log = ExportLog(tmp_path / "export_log.json")
        log.record("xml", _result(updated=["X"]))
        assert log.last_export is not None

    def test_persists_across_instances(self, tmp_path):
        path = tmp_path / "export_log.json"
        ExportLog(path).record("anilist", _result(updated=["Naruto"]))

        log2 = ExportLog(path)
        assert log2.get_target("anilist")["updated"] == 1
        assert log2.last_export is not None

    def test_empty_result_persists_zeros(self, tmp_path):
        log = ExportLog(tmp_path / "export_log.json")
        log.record("mal", _result())

        t = log.get_target("mal")
        assert t["updated"] == 0
        assert t["skipped"] == 0
        assert t["failed"] == []
