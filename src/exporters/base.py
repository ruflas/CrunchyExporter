from abc import ABC, abstractmethod
from src.crunchyroll.models import SeriesSummary


class ExportResult:
    def __init__(self):
        self.updated: list[str] = []
        self.skipped: list[str] = []
        self.failed: list[tuple[str, str]] = []

    @property
    def total(self) -> int:
        return len(self.updated) + len(self.skipped) + len(self.failed)


class BaseExporter(ABC):
    @abstractmethod
    def export(self, series: list[SeriesSummary]) -> ExportResult:
        ...
