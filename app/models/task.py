from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from enum import Enum

_id_counter = itertools.count(1)


class TaskStatus(str, Enum):
    PENDING = "等待中"
    DOWNLOADING = "下载中"
    MERGING = "合并中"
    DONE = "已完成"
    FAILED = "失败"


@dataclass
class DownloadTask:
    url: str
    preset: str
    out_dir: str
    id: int = field(default_factory=lambda: next(_id_counter))
    title: str = ""
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0          # 0-100
    speed: float = 0.0         # bytes/s
    eta: int = 0               # 秒
    error: str = ""

    @property
    def display_title(self) -> str:
        return self.title or self.url
