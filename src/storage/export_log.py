import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PATH = Path("data") / "export_log.json"


class ExportLog:
    def __init__(self, path: Path = DEFAULT_PATH):
        self.path = Path(path)
        self._data: dict = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def record(self, target: str, result) -> None:
        self._data["last_export"] = datetime.now(timezone.utc).isoformat()
        self._data.setdefault("targets", {})[target] = {
            "updated": len(result.updated),
            "skipped": len(result.skipped),
            "failed": [[t, r] for t, r in result.failed],
        }
        self.save()

    @property
    def last_export(self) -> str | None:
        return self._data.get("last_export")

    def get_target(self, target: str) -> dict | None:
        return self._data.get("targets", {}).get(target)
