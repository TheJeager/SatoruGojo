from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from satoru_gojo.config import settings
from satoru_gojo.database import Database
from satoru_gojo.utils.ffmpeg import build_ultra_low_latency_cmd
from satoru_gojo.utils.ytdlp import resolve_stream_url

LOGGER = logging.getLogger(__name__)


@dataclass
class StreamState:
    process: asyncio.subprocess.Process
    title: str
    source: str
    rtmp_url: str


class StreamManager:
    def __init__(self, db: Database):
        self.db = db
        self.states: dict[int, StreamState] = {}
        self.memory_rtmp: dict[int, str] = {}
        self.radio_presets: dict[str, str] = {
            "lofi": "https://play.streamafrica.net/lofiradio",
            "bbc": "http://stream.live.vc.bbcmedia.co.uk/bbc_world_service",
            "npr": "https://npr-ice.streamguys1.com/live.mp3",
            "jazz24": "https://live.wostreaming.net/direct/ppm-jazz24mp3-ibc1",
            "classic": "https://playerservices.streamtheworld.com/api/livestream-redirect/CLASSICFM_SC",
        }

    async def set_rtmp_key(self, chat_id: int, key: str, by_user: int) -> str:
        self.memory_rtmp[chat_id] = key
        await self.db.set_rtmp_key(chat_id, key, by_user)
        return self._build_rtmp_url(key)

    async def get_rtmp_url(self, chat_id: int) -> str | None:
        key = self.memory_rtmp.get(chat_id) or await self.db.get_rtmp_key(chat_id)
        if not key:
            return None
        self.memory_rtmp[chat_id] = key
        return self._build_rtmp_url(key)

    async def start_stream(self, chat_id: int, query_or_url: str, requested_by: int) -> str:
        await self.stop_stream(chat_id, silent=True)
        rtmp_url = await self.get_rtmp_url(chat_id)
        if not rtmp_url:
            raise ValueError("RTMP key not configured. Use /setrtmp <stream_key> first.")

        source_url, title = resolve_stream_url(query_or_url, settings.cookies_path)
        cmd = build_ultra_low_latency_cmd(settings.ffmpeg_bin, source_url, rtmp_url)
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self.states[chat_id] = StreamState(process=process, title=title, source=query_or_url, rtmp_url=rtmp_url)
        LOGGER.info("Started stream for chat %s: %s", chat_id, title)
        await self.db.add_stream_history(
            {
                "chat_id": chat_id,
                "requested_by": requested_by,
                "title": title,
                "source": query_or_url,
                "mode": "ytdlp",
                "status": "started",
            }
        )
        return title

    async def start_radio(self, chat_id: int, station: str, requested_by: int) -> str:
        await self.stop_stream(chat_id, silent=True)
        rtmp_url = await self.get_rtmp_url(chat_id)
        if not rtmp_url:
            raise ValueError("RTMP key not configured. Use /setrtmp <stream_key> first.")

        stream_url = self.radio_presets.get(station.lower())
        if not stream_url:
            raise ValueError(f"Unknown station '{station}'. Use /radio_list")

        cmd = build_ultra_low_latency_cmd(settings.ffmpeg_bin, stream_url, rtmp_url)
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        title = f"Radio: {station.lower()}"
        self.states[chat_id] = StreamState(process=process, title=title, source=stream_url, rtmp_url=rtmp_url)
        await self.db.add_stream_history(
            {
                "chat_id": chat_id,
                "requested_by": requested_by,
                "title": title,
                "source": stream_url,
                "mode": "radio",
                "status": "started",
            }
        )
        return title

    async def stop_stream(self, chat_id: int, silent: bool = False) -> bool:
        state = self.states.get(chat_id)
        if not state:
            return False
        if state.process.returncode is None:
            state.process.terminate()
            try:
                await asyncio.wait_for(state.process.wait(), timeout=6)
            except asyncio.TimeoutError:
                state.process.kill()
                await state.process.wait()
        self.states.pop(chat_id, None)
        if not silent:
            await self.db.add_stream_history({"chat_id": chat_id, "title": state.title, "status": "stopped"})
        return True

    def status(self, chat_id: int) -> str:
        state = self.states.get(chat_id)
        if not state:
            return "No active stream in this chat."
        status = "running" if state.process.returncode is None else f"exited({state.process.returncode})"
        return f"{state.title}\nSource: {state.source}\nStatus: {status}"

    def _build_rtmp_url(self, key: str) -> str:
        base = settings.default_rtmp_base.rstrip("/")
        return f"{base}/{key}"
