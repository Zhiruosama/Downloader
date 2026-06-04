from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from app.core import downloader

CookieMode = Literal["off", "browser", "file"]
BrowserName = Literal["chrome", "edge", "firefox"]


def _app_dir() -> Path:
    import os

    base = Path(os.getenv("APPDATA") or Path.home())
    path = base / "Downloader"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_download_dir() -> str:
    path = Path.home() / "Downloads"
    return str(path if path.exists() else Path.cwd())


@dataclass
class CookiesConfig:
    mode: CookieMode = "off"
    browser: BrowserName = "edge"
    cookieFile: str = ""


@dataclass
class AppConfig:
    defaultOutDir: str = default_download_dir()
    defaultPreset: str = downloader.DEFAULT_PRESET
    filenameTemplate: str = "%(title)s.%(ext)s"
    concurrency: int = 2
    cookies: CookiesConfig = field(default_factory=CookiesConfig)


class ConfigStore:
    def __init__(self) -> None:
        self.path = _app_dir() / "config.json"

    def load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig()
        try:
            with self.path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError):
            return AppConfig()

        cookies = raw.get("cookies") or {}
        return AppConfig(
            defaultOutDir=str(raw.get("defaultOutDir") or default_download_dir()),
            defaultPreset=str(raw.get("defaultPreset") or downloader.DEFAULT_PRESET),
            filenameTemplate=str(raw.get("filenameTemplate") or "%(title)s.%(ext)s"),
            concurrency=max(1, int(raw.get("concurrency") or 2)),
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

    def save(self, config: AppConfig) -> AppConfig:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(asdict(config), f, ensure_ascii=False, indent=2)
        return config
