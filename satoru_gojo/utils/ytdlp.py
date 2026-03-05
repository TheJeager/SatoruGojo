from __future__ import annotations

from typing import Any

import yt_dlp


def resolve_stream_url(query_or_url: str, cookies_path: str = "cookies.txt") -> tuple[str, str]:
    """Return direct media URL + title using resilient yt-dlp options."""

    opts: dict[str, Any] = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "quiet": True,
        "noplaylist": True,
        "default_search": "ytsearch",
        "extractor_retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 25,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "skip_download": True,
    }

    if cookies_path:
        opts["cookiefile"] = cookies_path

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(query_or_url, download=False)

    if "entries" in info and info["entries"]:
        info = info["entries"][0]

    media_url = info.get("url")
    title = info.get("title") or "Untitled"
    if not media_url:
        raise ValueError("yt-dlp failed to produce a playable media URL")

    return media_url, title
