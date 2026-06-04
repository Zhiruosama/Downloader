from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from enum import Enum
from time import time

_id_counter = itertools.count(1)


class TaskStatus(str, Enum):
    PENDING = "等待中"
    DOWNLOADING = "下载中"
    MERGING = "合并中"
    PAUSED = "已暂停"
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
    filepath: str = ""
    width: int = 0
    height: int = 0
    video_codec: str = ""
    audio_codec: str = ""
    created_at: float = field(default_factory=time)
    finished_at: float = 0.0

    @property
    def display_title(self) -> str:
        return self.title or self.url

    @property
    def spec_text(self) -> str:
        parts: list[str] = []
        if self.width and self.height:
            parts.append(f"{self.width}x{self.height}")
        elif self.height:
            parts.append(f"{self.height}p")
        if self.video_codec:
            parts.append(self.video_codec)
        if self.audio_codec:
            parts.append(self.audio_codec)
        return " / ".join(parts)
