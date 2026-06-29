from abc import ABC, abstractmethod
from src.crunchyroll.models import SeriesSummary


class ExportResult:
    def __init__(self):
        self.updated: list[str] = []
        self.skipped: list[str] = []
        self.failed: list[tuple[str, str]] = []
        # dry_run only: (series_id, title, human-readable description of the
        # change, actionable). actionable=False means this entry is informational
        # only (e.g. already up to date) and will be skipped regardless of
        # approval — used by the GUI to decide what needs a yes/no decision
        # in the per-series review flow.
        self.planned: list[tuple[str, str, str, bool]] = []

    @property
    def total(self) -> int:
        return len(self.updated) + len(self.skipped) + len(self.failed)


class BaseExporter(ABC):
    @abstractmethod
    def export(self, series: list[SeriesSummary], dry_run: bool = False) -> ExportResult:
        ...
