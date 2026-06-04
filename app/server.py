from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.core.queue_service import QueueService


def _default_download_dir() -> str:
    path = Path.home() / "Downloads"
    return str(path if path.exists() else Path.cwd())


class AddTasksRequest(BaseModel):
    urls: list[str]
    preset: str
    out_dir: str | None = None


class ConcurrencyRequest(BaseModel):
    value: int


app = FastAPI(title="Downloader Local API")
queue = QueueService()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "tauri://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/config")
def config() -> dict[str, Any]:
    return {
        "presets": queue.presets(),
        "defaultOutDir": os.getenv("DOWNLOADER_OUT_DIR") or _default_download_dir(),
    }


@app.get("/api/tasks")
def tasks() -> list[dict[str, Any]]:
    return queue.list_tasks()


@app.post("/api/tasks")
def add_tasks(payload: AddTasksRequest) -> list[dict[str, Any]]:
    out_dir = payload.out_dir or _default_download_dir()
    return queue.add_many(payload.urls, payload.preset, out_dir)


@app.post("/api/tasks/{task_id}/pause")
def pause(task_id: int) -> dict[str, bool]:
    queue.pause(task_id)
    return {"ok": True}


@app.post("/api/tasks/{task_id}/resume")
def resume(task_id: int) -> dict[str, bool]:
    queue.resume(task_id)
    return {"ok": True}


@app.post("/api/tasks/retry-failed")
def retry_failed() -> dict[str, bool]:
    queue.retry_failed()
    return {"ok": True}


@app.post("/api/tasks/clear-finished")
def clear_finished() -> dict[str, bool]:
    queue.clear_finished()
    return {"ok": True}


@app.post("/api/concurrency")
def set_concurrency(payload: ConcurrencyRequest) -> dict[str, bool]:
    queue.set_concurrency(payload.value)
    return {"ok": True}


@app.get("/api/history")
def history() -> list[dict[str, Any]]:
    return queue.list_history()


@app.post("/api/history/clear")
def clear_history() -> dict[str, bool]:
    queue.clear_history()
    return {"ok": True}
