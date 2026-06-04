from __future__ import annotations

import os
import shutil
import json
import subprocess
from dataclasses import dataclass
from typing import Callable, Optional

import yt_dlp


# MP4 兼容档: 优先 H.264 视频 + AAC(m4a) 音频, 兜底任意流, 合并为 mp4。
# 这样音频是 aac, 几乎所有播放器/设备都能正常播放且有声。
def _mp4_fmt(max_h: int) -> str:
    return (
        f"bestvideo[height<={max_h}][vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]/"
        f"bestvideo[height<={max_h}][ext=mp4]+bestaudio[ext=m4a]/"
        f"bestvideo[height<={max_h}]+bestaudio/"
        f"best[height<={max_h}]/best"
    )


# MKV 兼容档: 不限编码(可含 VP9/AV1/opus), 用 mkv 容器封装, 保证音画俱全。
def _mkv_fmt(max_h: Optional[int]) -> str:
    if max_h is None:
        return "bestvideo[height>0]+bestaudio/best[height>0]/best"
    return (
        f"bestvideo[height<={max_h}][height>0]+bestaudio/"
        f"best[height<={max_h}][height>0]/best"
    )


# 名称 -> (format 表达式, 合并容器 None=音频, 是否仅音频)
PRESETS: dict[str, tuple[str, Optional[str], bool]] = {
    "最高画质 (MKV, 保证音画)": (_mkv_fmt(None), "mkv", False),
    "4K 2160p (MKV)": (_mkv_fmt(2160), "mkv", False),
    "2K 1440p (MKV)": (_mkv_fmt(1440), "mkv", False),
    "1080p (MP4 兼容)": (_mp4_fmt(1080), "mp4", False),
    "720p (MP4 兼容)": (_mp4_fmt(720), "mp4", False),
    "480p (MP4 兼容)": (_mp4_fmt(480), "mp4", False),
    "仅音频 (MP3)": ("bestaudio/best", None, True),
}

DEFAULT_PRESET = "最高画质 (MKV, 保证音画)"


def _ffmpeg_dir() -> Optional[str]:
    """返回 ffmpeg 所在目录, 供 yt-dlp 合并/转码使用; 找不到返回 None。"""
    exe = shutil.which("ffmpeg")
    if not exe:
        return None
    return os.path.dirname(exe)


@dataclass
class MediaInfo:
    title: str
    uploader: str
    duration: int
    thumbnail: str
    webpage_url: str
    max_height: int


def _apply_cookies(opts: dict, cookies: Optional[dict]) -> None:
    if not cookies:
        return
    mode = cookies.get("mode")
    if mode == "browser":
        browser = cookies.get("browser") or "chrome"
        opts["cookiesfrombrowser"] = (browser,)
    elif mode == "file" and cookies.get("cookieFile"):
        opts["cookiefile"] = cookies["cookieFile"]


def extract_info(url: str, cookies: Optional[dict] = None) -> MediaInfo:
    """解析链接, 返回基本媒体信息 (不下载)。"""
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    _apply_cookies(opts, cookies)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return MediaInfo(
        title=info.get("title") or "未知标题",
        uploader=info.get("uploader") or info.get("channel") or "",
        duration=int(info.get("duration") or 0),
        thumbnail=info.get("thumbnail") or "",
        webpage_url=info.get("webpage_url") or url,
        max_height=max(
            (
                int(f.get("height") or 0)
                for f in info.get("formats", [])
                if f.get("vcodec") != "none"
            ),
            default=0,
        ),
    )


def _build_opts(
    preset: str,
    out_dir: str,
    progress_hook: Optional[Callable[[dict], None]],
    filename_template: str = "%(title)s.%(ext)s",
    cookies: Optional[dict] = None,
) -> dict:
    fmt, container, audio_only = PRESETS.get(preset, PRESETS[DEFAULT_PRESET])
    opts: dict = {
        "format": fmt,
        "outtmpl": {"default": filename_template or "%(title)s.%(ext)s"},
        "paths": {"home": out_dir},
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": False,
        "continuedl": True,
        "nopart": False,
        "retries": 5,
        "fragment_retries": 5,
    }
    if progress_hook is not None:
        opts["progress_hooks"] = [progress_hook]
        opts["postprocessor_hooks"] = [progress_hook]

    ff = _ffmpeg_dir()
    if ff:
        opts["ffmpeg_location"] = ff

    _apply_cookies(opts, cookies)

    if audio_only:
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
    elif container:
        opts["merge_output_format"] = container
    return opts


def download(
    url: str,
    preset: str,
    out_dir: str,
    progress_hook: Optional[Callable[[dict], None]] = None,
    filename_template: str = "%(title)s.%(ext)s",
    cookies: Optional[dict] = None,
) -> None:
    """同步下载 (建议在后台线程中调用)。"""
    opts = _build_opts(preset, out_dir, progress_hook, filename_template, cookies)
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])


def probe_media(path: str) -> dict[str, str | int]:
    """用 ffprobe 读取真实媒体规格。"""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {}
    ffprobe = os.path.join(os.path.dirname(ffmpeg), "ffprobe.exe")
    if not os.path.exists(ffprobe):
        ffprobe = shutil.which("ffprobe") or ""
    if not ffprobe or not os.path.exists(path):
        return {}

    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_streams",
            "-of",
            "json",
            path,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return {}
    data = json.loads(result.stdout or "{}")
    specs: dict[str, str | int] = {}
    for stream in data.get("streams", []):
        codec_type = stream.get("codec_type")
        if codec_type == "video" and not specs.get("height"):
            specs["width"] = int(stream.get("width") or 0)
            specs["height"] = int(stream.get("height") or 0)
            specs["video_codec"] = stream.get("codec_name") or ""
        elif codec_type == "audio" and not specs.get("audio_codec"):
            specs["audio_codec"] = stream.get("codec_name") or ""
    return specs
