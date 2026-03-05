from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    bot_token: str
    owner_id: int
    logger_id: int
    mongo_url: str
    default_rtmp_base: str
    cookies_path: str
    ffmpeg_bin: str


settings = Settings(
    api_id=int(os.getenv("API_ID", "0")),
    api_hash=os.getenv("API_HASH", ""),
    bot_token=os.getenv("BOT_TOKEN", ""),
    owner_id=int(os.getenv("OWNER_ID", "0")),
    logger_id=int(os.getenv("LOGGER_ID", "0")),
    mongo_url=os.getenv("MONGO_URL", ""),
    default_rtmp_base=os.getenv("DEFAULT_RTMP_BASE", "rtmps://dc5-1.rtmp.t.me/s/"),
    cookies_path=os.getenv("COOKIES_PATH", "cookies.txt"),
    ffmpeg_bin=os.getenv("FFMPEG_BIN", "ffmpeg"),
)


def validate_settings() -> None:
    missing = []
    if settings.api_id <= 0:
        missing.append("API_ID")
    if not settings.api_hash:
        missing.append("API_HASH")
    if not settings.bot_token:
        missing.append("BOT_TOKEN")
    if missing:
        raise RuntimeError(f"Missing required configuration values: {', '.join(missing)}")
