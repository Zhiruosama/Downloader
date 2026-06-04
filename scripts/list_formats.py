from __future__ import annotations

import sys

import yt_dlp


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python scripts/list_formats.py <url>")
        raise SystemExit(1)

    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(sys.argv[1], download=False)

    print(info.get("title") or "")
    print("format_id | ext | resolution | fps | vcodec | acodec | filesize")
    for f in info.get("formats", []):
        if f.get("vcodec") == "none":
            continue
        filesize = f.get("filesize") or f.get("filesize_approx") or ""
        print(
            f"{f.get('format_id','')} | {f.get('ext','')} | "
            f"{f.get('width') or ''}x{f.get('height') or ''} | "
            f"{f.get('fps') or ''} | {f.get('vcodec') or ''} | "
            f"{f.get('acodec') or ''} | {filesize}"
        )


if __name__ == "__main__":
    main()
