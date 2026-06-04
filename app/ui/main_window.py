from __future__ import annotations

import os

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core import downloader


def _fmt_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} PB"


def _fmt_eta(seconds) -> str:
    if not seconds:
        return "--:--"
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    return f"{m:02d}:{s:02d}"


class ProbeWorker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self) -> None:
        try:
            info = downloader.extract_info(self.url)
            self.done.emit(info)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class DownloadWorker(QThread):
    progress = Signal(dict)
    done = Signal()
    failed = Signal(str)

    def __init__(self, url: str, preset: str, out_dir: str):
        super().__init__()
        self.url = url
        self.preset = preset
        self.out_dir = out_dir

    def run(self) -> None:
        try:
            downloader.download(self.url, self.preset, self.out_dir, self._hook)
            self.done.emit()
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))

    def _hook(self, d: dict) -> None:
        self.progress.emit(d)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("多平台下载器")
        self.resize(640, 320)

        self._probe_worker: ProbeWorker | None = None
        self._dl_worker: DownloadWorker | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # 链接行
        url_row = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("粘贴视频链接...")
        self.probe_btn = QPushButton("解析")
        self.probe_btn.clicked.connect(self._on_probe)
        url_row.addWidget(self.url_edit)
        url_row.addWidget(self.probe_btn)
        root.addLayout(url_row)

        # 信息
        self.info_label = QLabel("尚未解析")
        self.info_label.setWordWrap(True)
        root.addWidget(self.info_label)

        # 格式行
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("格式:"))
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(list(downloader.PRESETS.keys()))
        fmt_row.addWidget(self.fmt_combo, 1)
        root.addLayout(fmt_row)

        # 目录行
        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("保存到:"))
        self.dir_edit = QLineEdit(self._default_dir())
        browse_btn = QPushButton("浏览")
        browse_btn.clicked.connect(self._on_browse)
        dir_row.addWidget(self.dir_edit, 1)
        dir_row.addWidget(browse_btn)
        root.addLayout(dir_row)

        # 下载按钮
        self.dl_btn = QPushButton("下载")
        self.dl_btn.clicked.connect(self._on_download)
        root.addWidget(self.dl_btn)

        # 进度
        self.progress = QProgressBar()
        self.progress.setValue(0)
        root.addWidget(self.progress)

        self.status_label = QLabel("就绪")
        root.addWidget(self.status_label)

        root.addStretch(1)

    def _default_dir(self) -> str:
        d = os.path.join(os.path.expanduser("~"), "Downloads")
        return d if os.path.isdir(d) else os.getcwd()

    # 解析
    def _on_probe(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            self.status_label.setText("请输入链接")
            return
        self.probe_btn.setEnabled(False)
        self.info_label.setText("解析中...")
        self._probe_worker = ProbeWorker(url)
        self._probe_worker.done.connect(self._on_probe_done)
        self._probe_worker.failed.connect(self._on_probe_failed)
        self._probe_worker.start()

    def _on_probe_done(self, info: downloader.MediaInfo) -> None:
        self.probe_btn.setEnabled(True)
        mins, secs = divmod(info.duration, 60)
        self.info_label.setText(
            f"标题: {info.title}\n作者: {info.uploader}    时长: {mins:02d}:{secs:02d}"
        )
        self.status_label.setText("解析完成")

    def _on_probe_failed(self, msg: str) -> None:
        self.probe_btn.setEnabled(True)
        self.info_label.setText("解析失败")
        self.status_label.setText(msg)

    # 目录
    def _on_browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择保存目录", self.dir_edit.text())
        if d:
            self.dir_edit.setText(d)

    # 下载
    def _on_download(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            self.status_label.setText("请输入链接")
            return
        out_dir = self.dir_edit.text().strip() or self._default_dir()
        os.makedirs(out_dir, exist_ok=True)
        preset = self.fmt_combo.currentText()

        self.dl_btn.setEnabled(False)
        self.probe_btn.setEnabled(False)
        self.progress.setValue(0)
        self.status_label.setText("开始下载...")

        self._dl_worker = DownloadWorker(url, preset, out_dir)
        self._dl_worker.progress.connect(self._on_progress)
        self._dl_worker.done.connect(self._on_download_done)
        self._dl_worker.failed.connect(self._on_download_failed)
        self._dl_worker.start()

    def _on_progress(self, d: dict) -> None:
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            if total:
                self.progress.setValue(int(done / total * 100))
            speed = d.get("speed") or 0
            eta = d.get("eta")
            self.status_label.setText(
                f"下载中  {_fmt_size(done)}/{_fmt_size(total)}  "
                f"{_fmt_size(speed)}/s  剩余 {_fmt_eta(eta)}"
            )
        elif status == "finished":
            self.progress.setValue(100)
            self.status_label.setText("下载完成, 后处理中...")

    def _on_download_done(self) -> None:
        self.dl_btn.setEnabled(True)
        self.probe_btn.setEnabled(True)
        self.progress.setValue(100)
        self.status_label.setText("全部完成")

    def _on_download_failed(self, msg: str) -> None:
        self.dl_btn.setEnabled(True)
        self.probe_btn.setEnabled(True)
        self.status_label.setText(f"失败: {msg}")
