from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from app.models.task import DownloadTask, TaskStatus


def _history_file() -> Path:
    base = Path(os.getenv("APPDATA") or Path.home())
    path = base / "Downloader" / "history.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


class HistoryStore:
    def __init__(self) -> None:
        self.path = _history_file()

    def load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return []
        return data if isinstance(data, list) else []

    def add(self, task: DownloadTask) -> None:
        records = self.load()
        item = asdict(task)
        item["status"] = (
            task.status.value if isinstance(task.status, TaskStatus) else str(task.status)
        )
        records.insert(0, item)
        del records[200:]
        self._save(records)

    def clear(self) -> None:
        self._save([])

    def _save(self, records: list[dict]) -> None:
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
