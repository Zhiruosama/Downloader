from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from app.core import downloader
from app.core.history import HistoryStore
from app.models.task import DownloadTask, TaskStatus


class _Cancelled(Exception):
    pass


class _Worker(QThread):
    progress = Signal(int, dict)   # task_id, yt-dlp hook dict
    done = Signal(int)             # task_id
    failed = Signal(int, str)      # task_id, error

    def __init__(self, task: DownloadTask):
        super().__init__()
        self.task = task
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            downloader.download(
                self.task.url, self.task.preset, self.task.out_dir, self._hook
            )
            self.done.emit(self.task.id)
        except _Cancelled:
            pass  # 用户主动取消, 静默结束
        except Exception as e:  # noqa: BLE001
            self.failed.emit(self.task.id, str(e))

    def _hook(self, d: dict) -> None:
        if self._cancel:
            raise _Cancelled()
        self.progress.emit(self.task.id, d)


class QueueManager(QObject):
    """管理下载任务队列与并发执行。"""

    task_added = Signal(object)     # DownloadTask
    task_updated = Signal(object)   # DownloadTask
    task_removed = Signal(int)      # task_id

    def __init__(self, max_concurrent: int = 2):
        super().__init__()
        self.max_concurrent = max(1, max_concurrent)
        self.history = HistoryStore()
        self.tasks: dict[int, DownloadTask] = {}
        self._workers: dict[int, _Worker] = {}
        self._pending: list[int] = []
        self._resume_after_pause: set[int] = set()

    # 外部接口
    def add(self, task: DownloadTask) -> None:
        self.tasks[task.id] = task
        self._pending.append(task.id)
        self.task_added.emit(task)
        self._pump()

    def set_concurrency(self, n: int) -> None:
        self.max_concurrent = max(1, n)
        self._pump()

    def retry(self, task_id: int) -> None:
        task = self.tasks.get(task_id)
        if not task or task.status != TaskStatus.FAILED:
            return
        task.status = TaskStatus.PENDING
        task.error = ""
        task.progress = 0
        self._pending.append(task_id)
        self.task_updated.emit(task)
        self._pump()

    def pause(self, task_id: int) -> None:
        task = self.tasks.get(task_id)
        if not task:
            return
        if task_id in self._pending:
            self._pending.remove(task_id)
            task.status = TaskStatus.PAUSED
            self.task_updated.emit(task)
            return
        worker = self._workers.get(task_id)
        if worker:
            task.status = TaskStatus.PAUSED
            task.speed = 0.0
            self.task_updated.emit(task)
            worker.cancel()

    def resume(self, task_id: int) -> None:
        task = self.tasks.get(task_id)
        if not task or task.status != TaskStatus.PAUSED:
            return
        if task_id in self._workers:
            self._resume_after_pause.add(task_id)
            return
        task.status = TaskStatus.PENDING
        task.error = ""
        self._pending.append(task_id)
        self.task_updated.emit(task)
        self._pump()

    def remove(self, task_id: int) -> None:
        """移除等待中或已结束的任务 (运行中的不移除)。"""
        if task_id in self._workers:
            return
        if task_id in self._pending:
            self._pending.remove(task_id)
        self.tasks.pop(task_id, None)
        self.task_removed.emit(task_id)

    def has_running(self) -> bool:
        return bool(self._workers)

    def shutdown(self) -> None:
        """请求取消所有运行中的任务并等待线程结束 (关闭程序时调用)。"""
        self._pending.clear()
        for worker in list(self._workers.values()):
            worker.cancel()
        for worker in list(self._workers.values()):
            worker.wait(5000)
        self._workers.clear()

    def clear_finished(self) -> None:
        for tid in [
            t.id
            for t in list(self.tasks.values())
            if t.status in (TaskStatus.DONE, TaskStatus.FAILED)
        ]:
            self.tasks.pop(tid, None)
            self.task_removed.emit(tid)

    # 内部调度
    def _pump(self) -> None:
        while len(self._workers) < self.max_concurrent and self._pending:
            self._start(self._pending.pop(0))

    def _start(self, task_id: int) -> None:
        task = self.tasks.get(task_id)
        if not task:
            return
        task.status = TaskStatus.DOWNLOADING
        worker = _Worker(task)
        worker.progress.connect(self._on_progress)
        worker.done.connect(self._on_done)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(lambda tid=task_id: self._discard(tid))
        self._workers[task_id] = worker
        self.task_updated.emit(task)
        worker.start()

    def _on_progress(self, task_id: int, d: dict) -> None:
        task = self.tasks.get(task_id)
        if not task:
            return
        if task.status == TaskStatus.PAUSED:
            return
        info = d.get("info_dict") or {}
        if info.get("title"):
            task.title = info["title"]
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            task.progress = int(done / total * 100) if total else 0
            task.speed = d.get("speed") or 0.0
            task.eta = d.get("eta") or 0
            task.status = TaskStatus.DOWNLOADING
        elif status == "finished":
            task.progress = 100
            task.speed = 0.0
            task.status = TaskStatus.MERGING
        self.task_updated.emit(task)

    def _on_done(self, task_id: int) -> None:
        from time import time

        task = self.tasks.get(task_id)
        if task:
            task.status = TaskStatus.DONE
            task.progress = 100
            task.speed = 0.0
            task.eta = 0
            task.finished_at = time()
            self.history.add(task)
            self.task_updated.emit(task)

    def _on_failed(self, task_id: int, msg: str) -> None:
        from time import time

        task = self.tasks.get(task_id)
        if task:
            task.status = TaskStatus.FAILED
            task.error = msg
            task.speed = 0.0
            task.finished_at = time()
            self.history.add(task)
            self.task_updated.emit(task)

    def _discard(self, task_id: int) -> None:
        """worker 线程结束后释放并发名额, 调度下一个。"""
        self._workers.pop(task_id, None)
        task = self.tasks.get(task_id)
        if task and task.status == TaskStatus.PAUSED and task_id in self._resume_after_pause:
            self._resume_after_pause.remove(task_id)
            task.status = TaskStatus.PENDING
            self._pending.append(task_id)
            self.task_updated.emit(task)
        self._pump()
