from __future__ import annotations

import os
import threading
from dataclasses import asdict
from time import time
from typing import Any

from app.core import downloader
from app.core.config_store import ConfigStore
from app.core.history import HistoryStore
from app.models.task import DownloadTask, TaskStatus


class Cancelled(Exception):
    pass


class QueueService:
    def __init__(self, max_concurrent: int = 2):
        self.config_store = ConfigStore()
        self.config = self.config_store.load()
        self.max_concurrent = max(1, self.config.concurrency or max_concurrent)
        self.history = HistoryStore()
        self.tasks: dict[int, DownloadTask] = {}
        self._pending: list[int] = []
        self._running: dict[int, threading.Thread] = {}
        self._cancelled: set[int] = set()
        self._lock = threading.RLock()

    def presets(self) -> list[str]:
        return list(downloader.PRESETS.keys())

    def get_config(self) -> dict[str, Any]:
        return {
            "presets": self.presets(),
            "defaultOutDir": self.config.defaultOutDir,
            "defaultPreset": self.config.defaultPreset,
            "filenameTemplate": self.config.filenameTemplate,
            "concurrency": self.config.concurrency,
            "cookies": {
                "mode": self.config.cookies.mode,
                "browser": self.config.cookies.browser,
                "cookieFile": self.config.cookies.cookieFile,
            },
        }

    def save_config(self, data: dict[str, Any]) -> dict[str, Any]:
        from app.core.config_store import AppConfig, CookiesConfig

        cookies = data.get("cookies") or {}
        config = AppConfig(
            defaultOutDir=str(data.get("defaultOutDir") or self.config.defaultOutDir),
            defaultPreset=str(data.get("defaultPreset") or self.config.defaultPreset),
            filenameTemplate=str(
                data.get("filenameTemplate") or self.config.filenameTemplate
            ),
            concurrency=max(1, int(data.get("concurrency") or self.config.concurrency)),
            cookies=CookiesConfig(
                mode=cookies.get("mode")
                if cookies.get("mode") in {"off", "browser", "file"}
                else "off",
                browser=cookies.get("browser")
                if cookies.get("browser") in {"chrome", "edge", "firefox"}
                else "chrome",
                cookieFile=str(cookies.get("cookieFile") or ""),
            ),
        )
        self.config = self.config_store.save(config)
        self.max_concurrent = self.config.concurrency
        return self.get_config()

    def probe(self, url: str) -> dict[str, Any]:
        info = downloader.extract_info(
            url,
            {
                "mode": self.config.cookies.mode,
                "browser": self.config.cookies.browser,
                "cookieFile": self.config.cookies.cookieFile,
            },
        )
        return {
            "title": info.title,
            "uploader": info.uploader,
            "duration": info.duration,
            "maxHeight": info.max_height,
            "url": info.webpage_url,
        }

    def add_many(
        self,
        urls: list[str],
        preset: str | None = None,
        out_dir: str | None = None,
    ) -> list[dict[str, Any]]:
        preset = preset or self.config.defaultPreset
        out_dir = out_dir or self.config.defaultOutDir
        os.makedirs(out_dir, exist_ok=True)
        added: list[DownloadTask] = []
        with self._lock:
            for url in urls[:30]:
                task = DownloadTask(url=url, preset=preset, out_dir=out_dir)
                self.tasks[task.id] = task
                self._pending.append(task.id)
                added.append(task)
            self._pump_locked()
        return [self._serialize(t) for t in added]

    def list_tasks(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._serialize(t) for t in self.tasks.values()]

    def list_history(self) -> list[dict[str, Any]]:
        return self.history.load()

    def set_concurrency(self, value: int) -> None:
        with self._lock:
            self.max_concurrent = max(1, value)
            self._pump_locked()

    def pause(self, task_id: int) -> None:
        with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return
            if task_id in self._pending:
                self._pending.remove(task_id)
            self._cancelled.add(task_id)
            task.status = TaskStatus.PAUSED
            task.speed = 0.0

    def resume(self, task_id: int) -> None:
        with self._lock:
            task = self.tasks.get(task_id)
            if not task or task.status != TaskStatus.PAUSED:
                return
            self._cancelled.discard(task_id)
            task.status = TaskStatus.PENDING
            task.error = ""
            self._pending.append(task_id)
            self._pump_locked()

    def retry_failed(self) -> None:
        with self._lock:
            for task in self.tasks.values():
                if task.status == TaskStatus.FAILED:
                    task.status = TaskStatus.PENDING
                    task.progress = 0
                    task.error = ""
                    self._pending.append(task.id)
            self._pump_locked()

    def clear_finished(self) -> None:
        with self._lock:
            for task_id, task in list(self.tasks.items()):
                if task.status in (TaskStatus.DONE, TaskStatus.FAILED):
                    self.tasks.pop(task_id, None)

    def clear_history(self) -> None:
        self.history.clear()

    def _pump_locked(self) -> None:
        while len(self._running) < self.max_concurrent and self._pending:
            task_id = self._pending.pop(0)
            if task_id in self._running:
                continue
            task = self.tasks.get(task_id)
            if not task:
                continue
            thread = threading.Thread(target=self._run_task, args=(task_id,), daemon=True)
            self._running[task_id] = thread
            task.status = TaskStatus.DOWNLOADING
            thread.start()

    def _run_task(self, task_id: int) -> None:
        task = self.tasks[task_id]
        try:
            downloader.download(
                task.url,
                task.preset,
                task.out_dir,
                self._hook(task_id),
                self.config.filenameTemplate,
                {
                    "mode": self.config.cookies.mode,
                    "browser": self.config.cookies.browser,
                    "cookieFile": self.config.cookies.cookieFile,
                },
            )
            with self._lock:
                if task.status != TaskStatus.PAUSED:
                    if task.filepath:
                        specs = downloader.probe_media(task.filepath)
                        task.width = int(specs.get("width") or task.width)
                        task.height = int(specs.get("height") or task.height)
                        task.video_codec = str(
                            specs.get("video_codec") or task.video_codec
                        )
                        task.audio_codec = str(
                            specs.get("audio_codec") or task.audio_codec
                        )
                    task.status = TaskStatus.DONE
                    task.progress = 100
                    task.speed = 0.0
                    task.eta = 0
                    task.finished_at = time()
                    self.history.add(task)
        except Cancelled:
            with self._lock:
                task.status = TaskStatus.PAUSED
                task.speed = 0.0
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                task.status = TaskStatus.FAILED
                task.error = str(exc)
                task.speed = 0.0
                task.finished_at = time()
                self.history.add(task)
        finally:
            with self._lock:
                self._running.pop(task_id, None)
                self._cancelled.discard(task_id)
                self._pump_locked()

    def _hook(self, task_id: int):
        def inner(data: dict) -> None:
            with self._lock:
                if task_id in self._cancelled:
                    raise Cancelled()
                task = self.tasks.get(task_id)
                if not task:
                    return
                info = data.get("info_dict") or {}
                self._apply_info(task, data, info)
        return inner

    def _apply_info(self, task: DownloadTask, data: dict, info: dict) -> None:
        if info.get("title"):
            task.title = info["title"]
        filepath = (
            data.get("filepath")
            or data.get("filename")
            or info.get("filepath")
            or info.get("_filename")
        )
        if filepath:
            task.filepath = filepath
        if info.get("width"):
            task.width = int(info["width"])
        if info.get("height"):
            task.height = int(info["height"])
        if info.get("vcodec") and info.get("vcodec") != "none":
            task.video_codec = info["vcodec"]
        if info.get("acodec") and info.get("acodec") != "none":
            task.audio_codec = info["acodec"]

        status = data.get("status")
        if status == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            done = data.get("downloaded_bytes") or 0
            task.progress = int(done / total * 100) if total else 0
            task.speed = data.get("speed") or 0.0
            task.eta = data.get("eta") or 0
            task.status = TaskStatus.DOWNLOADING
        elif status == "finished":
            task.progress = 100
            task.speed = 0.0
            task.status = TaskStatus.MERGING

    def _serialize(self, task: DownloadTask) -> dict[str, Any]:
        data = asdict(task)
        data["status"] = task.status.value
        data["display_title"] = task.display_title
        data["spec_text"] = task.spec_text
        return data

    def _friendly_error(self, message: str) -> str:
        lower = message.lower()
        if "could not copy" in lower and "cookie database" in lower:
            return (
                "浏览器 cookies 数据库正在被占用或无法复制。请先完全关闭对应浏览器"
                "(包括后台进程),再点击检测；更推荐导出 cookies.txt 后在设置中使用。"
            )
        if "cookie database" in lower:
            return "读取浏览器 cookies 失败。请关闭浏览器后重试,或改用 cookies.txt。"
        if "cookies" in lower or "login" in lower or "sign in" in lower:
            return "未读取到有效登录态。请先在浏览器登录目标网站,再点击检测。"
        if "private" in lower or "permission" in lower:
            return "当前账号没有访问权限,或内容需要会员/私密权限。"
        if "unsupported url" in lower:
            return "链接暂不支持或格式不正确。"
        return message[:300]
