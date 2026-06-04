from __future__ import annotations

import os
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core import downloader
from app.core.queue_manager import QueueManager
from app.models.task import DownloadTask, TaskStatus

COL_TITLE, COL_FORMAT, COL_SPEC, COL_STATUS, COL_PROGRESS, COL_SPEED = range(6)


def _fmt_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} PB"


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("多平台下载器")
        self.resize(920, 620)

        self.queue = QueueManager(max_concurrent=2)
        self.queue.task_added.connect(self._on_task_added)
        self.queue.task_updated.connect(self._on_task_updated)
        self.queue.task_removed.connect(self._on_task_removed)

        self._row_of: dict[int, int] = {}   # task_id -> 表格行

        self._build_ui()
        self._load_history()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # 链接行
        url_row = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("粘贴视频链接, 回车或点击加入队列...")
        self.url_edit.returnPressed.connect(self._on_add)
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(list(downloader.PRESETS.keys()))
        add_btn = QPushButton("加入队列")
        add_btn.clicked.connect(self._on_add)
        url_row.addWidget(self.url_edit, 1)
        url_row.addWidget(self.fmt_combo)
        url_row.addWidget(add_btn)
        root.addLayout(url_row)

        # 目录行
        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("保存到:"))
        self.dir_edit = QLineEdit(self._default_dir())
        browse_btn = QPushButton("浏览")
        browse_btn.clicked.connect(self._on_browse)
        dir_row.addWidget(self.dir_edit, 1)
        dir_row.addWidget(browse_btn)
        root.addLayout(dir_row)

        # 任务表格
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["标题", "格式", "实际规格", "状态", "进度", "速度"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(COL_TITLE, QHeaderView.Stretch)
        for c in (COL_FORMAT, COL_SPEC, COL_STATUS, COL_PROGRESS, COL_SPEED):
            hh.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        root.addWidget(self.table, 1)

        # 控制行
        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("同时下载:"))
        self.conc_spin = QSpinBox()
        self.conc_spin.setRange(1, 8)
        self.conc_spin.setValue(2)
        self.conc_spin.valueChanged.connect(self.queue.set_concurrency)
        ctrl_row.addWidget(self.conc_spin)
        ctrl_row.addStretch(1)
        pause_btn = QPushButton("暂停/继续")
        pause_btn.clicked.connect(self._on_pause_resume)
        retry_btn = QPushButton("重试失败")
        retry_btn.clicked.connect(self._on_retry)
        remove_btn = QPushButton("移除所选")
        remove_btn.clicked.connect(self._on_remove)
        clear_btn = QPushButton("清除已完成")
        clear_btn.clicked.connect(self.queue.clear_finished)
        ctrl_row.addWidget(pause_btn)
        ctrl_row.addWidget(retry_btn)
        ctrl_row.addWidget(remove_btn)
        ctrl_row.addWidget(clear_btn)
        root.addLayout(ctrl_row)

        # 历史记录
        root.addWidget(QLabel("历史记录:"))
        self.history_table = QTableWidget(0, 6)
        self.history_table.setHorizontalHeaderLabels(["时间", "标题", "格式", "实际规格", "状态", "文件"])
        self.history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        hh2 = self.history_table.horizontalHeader()
        hh2.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh2.setSectionResizeMode(1, QHeaderView.Stretch)
        for c in (2, 3, 4, 5):
            hh2.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        root.addWidget(self.history_table, 1)

        hist_row = QHBoxLayout()
        hist_row.addStretch(1)
        clear_hist_btn = QPushButton("清空历史")
        clear_hist_btn.clicked.connect(self._on_clear_history)
        hist_row.addWidget(clear_hist_btn)
        root.addLayout(hist_row)

    def _default_dir(self) -> str:
        d = os.path.join(os.path.expanduser("~"), "Downloads")
        return d if os.path.isdir(d) else os.getcwd()

    # 操作
    def _on_add(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            return
        out_dir = self.dir_edit.text().strip() or self._default_dir()
        os.makedirs(out_dir, exist_ok=True)
        task = DownloadTask(url=url, preset=self.fmt_combo.currentText(), out_dir=out_dir)
        self.queue.add(task)
        self.url_edit.clear()

    def _on_browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择保存目录", self.dir_edit.text())
        if d:
            self.dir_edit.setText(d)

    def _selected_task_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, COL_TITLE)
        return item.data(Qt.UserRole) if item else None

    def _on_retry(self) -> None:
        tid = self._selected_task_id()
        if tid is not None:
            self.queue.retry(tid)

    def _on_pause_resume(self) -> None:
        tid = self._selected_task_id()
        if tid is None:
            return
        task = self.queue.tasks.get(tid)
        if not task:
            return
        if task.status == TaskStatus.PAUSED:
            self.queue.resume(tid)
        elif task.status in (TaskStatus.PENDING, TaskStatus.DOWNLOADING):
            self.queue.pause(tid)

    def _on_remove(self) -> None:
        tid = self._selected_task_id()
        if tid is None:
            return
        task = self.queue.tasks.get(tid)
        if task and task.status == TaskStatus.DOWNLOADING:
            QMessageBox.information(self, "提示", "下载中的任务无法移除")
            return
        self.queue.remove(tid)

    # 队列信号
    def _on_task_added(self, task: DownloadTask) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._row_of[task.id] = row

        title_item = QTableWidgetItem(task.display_title)
        title_item.setData(Qt.UserRole, task.id)
        self.table.setItem(row, COL_TITLE, title_item)
        self.table.setItem(row, COL_FORMAT, QTableWidgetItem(task.preset))
        self.table.setItem(row, COL_SPEC, QTableWidgetItem(task.spec_text))
        self.table.setItem(row, COL_STATUS, QTableWidgetItem(task.status.value))

        bar = QProgressBar()
        bar.setValue(0)
        self.table.setCellWidget(row, COL_PROGRESS, bar)
        self.table.setItem(row, COL_SPEED, QTableWidgetItem(""))

    def _on_task_updated(self, task: DownloadTask) -> None:
        row = self._row_of.get(task.id)
        if row is None:
            return
        self.table.item(row, COL_TITLE).setText(task.display_title)
        self.table.item(row, COL_SPEC).setText(task.spec_text)
        status_text = task.status.value
        if task.status == TaskStatus.FAILED and task.error:
            status_text = f"失败: {task.error[:40]}"
        self.table.item(row, COL_STATUS).setText(status_text)

        bar = self.table.cellWidget(row, COL_PROGRESS)
        if bar:
            bar.setValue(task.progress)

        speed_text = f"{_fmt_size(task.speed)}/s" if task.speed else ""
        self.table.item(row, COL_SPEED).setText(speed_text)
        if task.status in (TaskStatus.DONE, TaskStatus.FAILED):
            self._load_history()

    def _on_task_removed(self, task_id: int) -> None:
        row = self._row_of.pop(task_id, None)
        if row is None:
            return
        self.table.removeRow(row)
        # 行号变动, 重建映射
        self._rebuild_row_map()

    def _rebuild_row_map(self) -> None:
        self._row_of.clear()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, COL_TITLE)
            if item:
                self._row_of[item.data(Qt.UserRole)] = row

    def _load_history(self) -> None:
        records = self.queue.history.load()
        self.history_table.setRowCount(0)
        for item in records:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)
            finished = item.get("finished_at") or item.get("created_at") or 0
            when = (
                time.strftime("%Y-%m-%d %H:%M", time.localtime(float(finished)))
                if finished
                else ""
            )
            title = item.get("title") or item.get("url") or ""
            spec = self._spec_from_history(item)
            values = [
                when,
                title,
                item.get("preset") or "",
                spec,
                item.get("status") or "",
                item.get("filepath") or item.get("out_dir") or "",
            ]
            for col, value in enumerate(values):
                self.history_table.setItem(row, col, QTableWidgetItem(str(value)))

    def _on_clear_history(self) -> None:
        self.queue.history.clear()
        self._load_history()

    def _spec_from_history(self, item: dict) -> str:
        parts: list[str] = []
        width = int(item.get("width") or 0)
        height = int(item.get("height") or 0)
        if width and height:
            parts.append(f"{width}x{height}")
        elif height:
            parts.append(f"{height}p")
        if item.get("video_codec"):
            parts.append(str(item["video_codec"]))
        if item.get("audio_codec"):
            parts.append(str(item["audio_codec"]))
        return " / ".join(parts)

    def closeEvent(self, event) -> None:
        if self.queue.has_running():
            reply = QMessageBox.question(
                self,
                "确认退出",
                "仍有任务正在下载, 确定要退出并取消吗?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                event.ignore()
                return
        self.queue.shutdown()
        event.accept()
