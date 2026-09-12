import asyncio
import logging
import os
import subprocess
import tempfile
import threading
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Deque, Dict, List, Optional, Tuple

import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import (
    API_HASH,
    API_ID,
    BOT_TOKEN,
    DEFAULT_RTMP_URL,
    LOGGER_ID,
    MONGO_URL,
    OWNER_ID,
    YTDLP_COOKIE_FILE,
    YTDLP_PROXY,
)
from database import Database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger("GojoSatoru")

bot = Client("RTMPBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
db = Database(MONGO_URL)

rtmp_keys: Dict[int, str] = {}
queues: Dict[int, Deque[dict]] = defaultdict(deque)
queue_locks: Dict[int, threading.Lock] = defaultdict(threading.Lock)
worker_locks: Dict[int, threading.Lock] = defaultdict(threading.Lock)
worker_running: Dict[int, bool] = defaultdict(bool)
ffmpeg_processes: Dict[int, Optional[subprocess.Popen]] = {}
stream_status: Dict[int, str] = {}
stop_requested: set[int] = set()
skip_requested: set[int] = set()

WELCOME_IMAGE = "https://i.ibb.co/QFt3Z9bC/tmpg1y9wbs8.jpg"


def build_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Quick Start", callback_data="help_quick")],
            [
                InlineKeyboardButton("Stream Commands", callback_data="help_stream"),
                InlineKeyboardButton("Control", callback_data="help_control"),
            ],
            [
                InlineKeyboardButton("Info", callback_data="help_info"),
                InlineKeyboardButton("Admin", callback_data="help_admin"),
            ],
            [
                InlineKeyboardButton("Support", url="https://t.me/RadhaSprt"),
                InlineKeyboardButton("Updates", url="https://t.me/CodingAssociation"),
            ],
        ]
    )


def build_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅ Back", callback_data="home")]]
    )


def get_start_text(username: Optional[str]) -> str:
    mention = f"@{username}" if username else "there"
    return (
        f"Hello {mention}\n\n"
        "I am Gojo Satoru, your RTMP streaming assistant for Telegram.\n\n"
        "Quick Setup\n"
        "1) Use /setkey <your_key>\n"
        "2) Reply to media with /play\n"
        "3) Or use /uplay, /ytplay or /ytaudio\n\n"
        "Tap a category below for help."
    )


HELP_SECTIONS = {
    "help_quick": (
        "Quick Start",
        "Start Here\n\n"
        "• /setkey <key> → set your RTMP stream key\n"
        "• /play → reply to audio/video media\n"
        "• /playaudio → reply to media for audio-only streaming\n"
        "• /uplay <url> → stream from a direct media URL",
    ),
    "help_stream": (
        "Stream Commands",
        "Streaming\n\n"
        "• /play\n"
        "• /playaudio\n"
        "• /uplay <url>\n"
        "• /ytplay <query or URL>\n"
        "• /ytaudio <query or URL>",
    ),
    "help_control": (
        "Control Commands",
        "Control\n\n"
        "• /stop → stop current stream and clear queue\n"
        "• /skip → skip current stream\n"
        "• /queue → view queued items",
    ),
    "help_info": (
        "Info Commands",
        "Information\n\n"
        "• /status → current stream state\n"
        "• /stats → your stream statistics\n"
        "• /ping → Telegram response latency\n"
        "• /help → open help",
    ),
    "help_admin": (
        "Admin Commands",
        "Admin\n\n"
        "• /broadcast <message> → broadcast to registered users\n"
        "• /setkey <key> → configure the chat RTMP key",
    ),
}


def format_duration(seconds: int) -> str:
    try:
        seconds = max(0, int(seconds or 0))
    except (TypeError, ValueError):
        seconds = 0
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"


def media_file_name(message: Message) -> str:
    media = message.audio or message.video or message.document or message.voice
    return getattr(media, "file_name", None) or "Media"


def media_duration(message: Message) -> int:
    media = message.audio or message.video or message.voice
    return int(getattr(media, "duration", 0) or 0)


def media_has_video(message: Message) -> bool:
    return bool(message.video or message.animation)


def get_rtmp_url(chat_id: int) -> Optional[str]:
    key = rtmp_keys.get(chat_id)
    if not key:
        return None
    base = DEFAULT_RTMP_URL.rstrip("/")
    return f"{base}/{key.lstrip('/')}"


def build_ffmpeg_local(input_file: str, rtmp_url: str, has_video: bool) -> List[str]:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-re",
        "-i",
        input_file,
    ]
    if has_video:
        command += [
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-tune",
            "zerolatency",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
            "-r",
            "30",
            "-g",
            "60",
            "-keyint_min",
            "60",
            "-b:v",
            "2000k",
            "-maxrate",
            "2200k",
            "-bufsize",
            "4000k",
        ]
    else:
        command += ["-vn"]
    command += [
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ac",
        "2",
        "-ar",
        "44100",
        "-flvflags",
        "no_duration_filesize",
        "-f",
        "flv",
        rtmp_url,
    ]
    return command


def build_ffmpeg_network(input_url: str, rtmp_url: str, has_video: bool = True) -> List[str]:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-re",
        "-i",
        input_url,
    ]
    if has_video:
        command += [
            "-map",
            "0:v:0?",
            "-map",
            "0:a:0?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-tune",
            "zerolatency",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
            "-r",
            "30",
            "-g",
            "60",
            "-keyint_min",
            "60",
            "-b:v",
            "2000k",
            "-maxrate",
            "2200k",
            "-bufsize",
            "4000k",
        ]
    else:
        command += ["-vn"]
    command += [
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ac",
        "2",
        "-ar",
        "44100",
        "-flvflags",
        "no_duration_filesize",
        "-f",
        "flv",
        rtmp_url,
    ]
    return command


def ytdlp_options(video: bool) -> dict:
    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        "format": "best[height<=720][vcodec!=none][acodec!=none]/best" if video else "bestaudio/best",
    }
    if YTDLP_COOKIE_FILE and os.path.isfile(YTDLP_COOKIE_FILE):
        options["cookiefile"] = YTDLP_COOKIE_FILE
    if YTDLP_PROXY:
        options["proxy"] = YTDLP_PROXY
    return options


def ytdl_extract(query: str, video: bool) -> Optional[dict]:
    try:
        with yt_dlp.YoutubeDL(ytdlp_options(video)) as ydl:
            info = ydl.extract_info(query, download=False)
            if info and info.get("entries"):
                info = next((entry for entry in info["entries"] if entry), None)
            return info
    except Exception as exc:
        logger.exception("yt-dlp extraction failed: %s", exc)
        return None


def process_alive(chat_id: int) -> bool:
    process = ffmpeg_processes.get(chat_id)
    return bool(process and process.poll() is None)


def enqueue_item(item: dict) -> None:
    chat_id = item["chat_id"]
    with queue_locks[chat_id]:
        queues[chat_id].append(item)
    ensure_worker(chat_id)


def terminate_process(chat_id: int) -> None:
    process = ffmpeg_processes.get(chat_id)
    if not process:
        return
    try:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
    except (ProcessLookupError, OSError, subprocess.TimeoutExpired):
        pass
    finally:
        ffmpeg_processes[chat_id] = None


def ensure_worker(chat_id: int) -> None:
    with worker_locks[chat_id]:
        if worker_running[chat_id]:
            return
        worker_running[chat_id] = True
        threading.Thread(target=stream_worker, args=(chat_id,), daemon=True).start()


def run_async(coro) -> None:
    try:
        asyncio.run(coro)
    except Exception:
        logger.exception("Background async operation failed")


def record_stat(item: dict, duration: float, status: str) -> None:
    run_async(
        db.add_stream_stat(
            user_id=item.get("user_id"),
            username=item.get("username", "unknown"),
            title=item.get("title", "Unknown"),
            duration=duration,
            stream_type=item.get("stream_type", "UNKNOWN"),
            status=status,
            chat_id=item.get("chat_id"),
        )
    )


def stream_worker(chat_id: int) -> None:
    try:
        while True:
            with queue_locks[chat_id]:
                item = queues[chat_id].popleft() if queues[chat_id] else None
            if item is None:
                stream_status[chat_id] = "idle"
                return

            rtmp_url = get_rtmp_url(chat_id)
            if not rtmp_url:
                stream_status[chat_id] = "error"
                run_async(item["msg"].edit("No RTMP key configured."))
                continue

            stream_status[chat_id] = "starting"
            run_async(item["msg"].edit(item["caption"]))
            command = item["ffmpeg_cmd"]
            started = time.monotonic()
            status = "completed"
            process = None

            try:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL,
                    text=True,
                )
                ffmpeg_processes[chat_id] = process
                stream_status[chat_id] = "streaming"
                _, stderr = process.communicate()
                return_code = process.returncode
                if chat_id in stop_requested:
                    status = "stopped"
                elif chat_id in skip_requested:
                    status = "skipped"
                elif return_code != 0:
                    status = "error"
                    error_text = (stderr or "").strip()[-500:]
                    if error_text:
                        logger.error("FFmpeg chat %s: %s", chat_id, error_text)
            except Exception as exc:
                status = "error"
                logger.exception("FFmpeg worker failed for chat %s: %s", chat_id, exc)
            finally:
                ffmpeg_processes[chat_id] = None
                duration = max(0.0, time.monotonic() - started)
                record_stat(item, duration, status)
                input_file = item.get("input_file")
                if input_file and os.path.exists(input_file):
                    try:
                        os.unlink(input_file)
                    except OSError:
                        pass
                if chat_id in skip_requested:
                    skip_requested.discard(chat_id)
                if chat_id in stop_requested:
                    stop_requested.discard(chat_id)
                stream_status[chat_id] = status
    finally:
        with worker_locks[chat_id]:
            worker_running[chat_id] = False
        if queues.get(chat_id):
            ensure_worker(chat_id)


async def send_log(
    user_id: int,
    username: str,
    chat_id: int,
    action: str,
    title: str = "",
    duration: str = "",
) -> None:
    if not LOGGER_ID:
        return
    text = f"[{action}]\nUser: @{username} (ID: {user_id})\nChat: {chat_id}"
    if title:
        text += f"\nTitle: {title}"
    if duration:
        text += f"\nDuration: {duration}"
    text += f"\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    try:
        await bot.send_message(LOGGER_ID, text)
    except Exception:
        logger.exception("Failed to send log")


def is_admin(user_id: int) -> bool:
    return user_id == OWNER_ID


async def load_key(chat_id: int) -> Optional[str]:
    key = rtmp_keys.get(chat_id)
    if key:
        return key
    key = await db.get_rtmp_key(chat_id)
    if key:
        rtmp_keys[chat_id] = key
    return key


@bot.on_message(filters.command("start"))
async def start(_, m: Message):
    if not m.from_user:
        return
    await db.add_user(m.from_user.id, m.from_user.username or "unknown")
    buttons = build_home_keyboard()
    text = get_start_text(m.from_user.username)
    try:
        await m.reply_photo(photo=WELCOME_IMAGE, caption=text, reply_markup=buttons)
    except Exception:
        await m.reply(text, reply_markup=buttons)


@bot.on_callback_query(filters.regex("^help_(quick|stream|control|info|admin)$"))
async def show_help_section(_, query: CallbackQuery):
    await query.answer()
    _, body = HELP_SECTIONS.get(query.data, ("Help", "No help section found."))
    await query.message.edit_text(body, reply_markup=build_back_keyboard())


@bot.on_callback_query(filters.regex("^home$"))
async def show_home(_, query: CallbackQuery):
    await query.answer()
    text = get_start_text(query.from_user.username)
    try:
        await query.message.edit_caption(caption=text, reply_markup=build_home_keyboard())
    except Exception:
        try:
            await query.message.edit_text(text, reply_markup=build_home_keyboard())
        except Exception:
            pass


@bot.on_message(filters.command("setkey"))
async def setkey(_, m: Message):
    if not m.from_user or not is_admin(m.from_user.id):
        return await m.reply("Unauthorized.")
    if len(m.command) < 2:
        return await m.reply("Usage: /setkey <RTMP_KEY>")
    key = m.command[1].strip()
    if not key or len(key) > 512:
        return await m.reply("Invalid RTMP key.")
    rtmp_keys[m.chat.id] = key
    await db.set_rtmp_key(m.chat.id, key)
    await m.reply("RTMP key configured and saved.")
    await send_log(m.from_user.id, m.from_user.username or "unknown", m.chat.id, "SETKEY")


@bot.on_message(filters.command("ping"))
async def ping(_, m: Message):
    started = time.perf_counter()
    reply = await m.reply("Measuring latency...")
    latency = int((time.perf_counter() - started) * 1000)
    await reply.edit_text(f"Latency: {latency}ms")


@bot.on_message(filters.command("status"))
async def status(_, m: Message):
    await load_key(m.chat.id)
    state = stream_status.get(m.chat.id, "idle")
    with queue_locks[m.chat.id]:
        queued = len(queues[m.chat.id])
    await m.reply(f"Stream status: {state}\nQueue: {queued}")


@bot.on_message(filters.command("stats"))
async def stats(_, m: Message):
    if not m.from_user:
        return
    user_stats = await db.get_user_stats(m.from_user.id)
    await m.reply(
        "Stream Statistics\n\n"
        f"Total Streams: {user_stats.get('total_streams', 0)}\n"
        f"Successful Streams: {user_stats.get('successful_streams', 0)}\n"
        f"Failed Streams: {user_stats.get('failed_streams', 0)}\n"
        f"Total Stream Time: {int(user_stats.get('total_duration', 0))} seconds\n"
        f"Average Stream Time: {int(user_stats.get('avg_duration', 0))} seconds"
    )


@bot.on_message(filters.command("stop"))
async def stop(_, m: Message):
    with queue_locks[m.chat.id]:
        queues[m.chat.id].clear()
    stop_requested.add(m.chat.id)
    await asyncio.to_thread(terminate_process, m.chat.id)
    stream_status[m.chat.id] = "stopped"
    await m.reply("Stream stopped and queue cleared.")
    if m.from_user:
        await send_log(m.from_user.id, m.from_user.username or "unknown", m.chat.id, "STOP")


@bot.on_message(filters.command("skip"))
async def skip(_, m: Message):
    if not process_alive(m.chat.id):
        return await m.reply("No active stream to skip.")
    skip_requested.add(m.chat.id)
    await asyncio.to_thread(terminate_process, m.chat.id)
    await m.reply("Current stream skipped.")
    if m.from_user:
        await send_log(m.from_user.id, m.from_user.username or "unknown", m.chat.id, "SKIP")


@bot.on_message(filters.command("queue"))
async def show_queue(_, m: Message):
    with queue_locks[m.chat.id]:
        items = list(queues[m.chat.id])
    if not items:
        return await m.reply("Queue is empty.")
    lines = ["QUEUE:"]
    for index, item in enumerate(items, 1):
        lines.append(f"{index}. {item.get('title', 'Unknown')} ({item.get('duration', 'Unknown')})")
    await m.reply("\n".join(lines))


@bot.on_message(filters.command("broadcast"))
async def broadcast(_, m: Message):
    if not m.from_user or not is_admin(m.from_user.id):
        return await m.reply("Unauthorized.")
    if len(m.command) < 2:
        return await m.reply("Usage: /broadcast <message>")
    message = m.text.split(maxsplit=1)[1]
    users = await db.get_all_users()
    sent = 0
    for user in users:
        try:
            await bot.send_message(user["user_id"], message)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            continue
    await db.add_broadcast(m.from_user.id, message, sent)
    await m.reply(f"Broadcast sent to {sent} users.")


async def create_local_item(m: Message, audio_only: bool = False) -> Optional[dict]:
    reply = m.reply_to_message
    if not reply or not (reply.audio or reply.voice or reply.video or reply.document):
        await m.reply("Reply to an audio or video file.")
        return None

    rtmp_url = get_rtmp_url(m.chat.id)
    if not rtmp_url:
        await load_key(m.chat.id)
        rtmp_url = get_rtmp_url(m.chat.id)
    if not rtmp_url:
        await m.reply("Set RTMP key first using /setkey.")
        return None

    msg = await m.reply("Downloading media...")
    filename = media_file_name(reply)
    extension = os.path.splitext(filename)[1] or ".media"
    fd, filepath = tempfile.mkstemp(prefix="gojo_", suffix=extension)
    os.close(fd)

    try:
        await reply.download(file_name=filepath)
    except Exception as exc:
        try:
            os.unlink(filepath)
        except OSError:
            pass
        await msg.edit(f"Download failed: {str(exc)[:120]}")
        return None

    duration = format_duration(media_duration(reply))
    has_video = media_has_video(reply) and not audio_only
    title = filename
    return {
        "chat_id": m.chat.id,
        "title": title,
        "duration": duration,
        "caption": f"Streaming{' (Audio)' if audio_only else ''}: {title}\nDuration: {duration}",
        "msg": msg,
        "input_file": filepath,
        "ffmpeg_cmd": build_ffmpeg_local(filepath, rtmp_url, has_video),
        "user_id": m.from_user.id if m.from_user else 0,
        "username": m.from_user.username if m.from_user and m.from_user.username else "unknown",
        "stream_type": "PLAYAUDIO" if audio_only else "PLAY",
    }


@bot.on_message(filters.command("play"))
async def play(_, m: Message):
    item = await create_local_item(m, audio_only=False)
    if not item:
        return
    enqueue_item(item)
    await item["msg"].edit(f"Queued: {item['title']}")
    if m.from_user:
        await send_log(m.from_user.id, m.from_user.username or "unknown", m.chat.id, "PLAY", item["title"], item["duration"])


@bot.on_message(filters.command("playaudio"))
async def playaudio(_, m: Message):
    item = await create_local_item(m, audio_only=True)
    if not item:
        return
    enqueue_item(item)
    await item["msg"].edit(f"Queued: {item['title']}")
    if m.from_user:
        await send_log(m.from_user.id, m.from_user.username or "unknown", m.chat.id, "PLAYAUDIO", item["title"], item["duration"])


@bot.on_message(filters.command("uplay"))
async def uplay(_, m: Message):
    if len(m.command) < 2:
        return await m.reply("Usage: /uplay <url>")
    await load_key(m.chat.id)
    rtmp_url = get_rtmp_url(m.chat.id)
    if not rtmp_url:
        return await m.reply("Set RTMP key first using /setkey.")
    media_url = m.text.split(maxsplit=1)[1].strip()
    if not media_url.startswith(("http://", "https://")):
        return await m.reply("Only HTTP(S) media URLs are supported.")
    msg = await m.reply("Queued: Direct URL")
    item = {
        "chat_id": m.chat.id,
        "title": "Direct URL",
        "duration": "Unknown",
        "caption": "Streaming from URL",
        "msg": msg,
        "ffmpeg_cmd": build_ffmpeg_network(media_url, rtmp_url, True),
        "user_id": m.from_user.id if m.from_user else 0,
        "username": m.from_user.username if m.from_user and m.from_user.username else "unknown",
        "stream_type": "UPLAY",
    }
    enqueue_item(item)


async def create_ytdlp_item(m: Message, video: bool) -> Optional[dict]:
    if len(m.command) < 2:
        await m.reply(f"Usage: /{'ytplay' if video else 'ytaudio'} <query or URL>")
        return None
    await load_key(m.chat.id)
    rtmp_url = get_rtmp_url(m.chat.id)
    if not rtmp_url:
        await m.reply("Set RTMP key first using /setkey.")
        return None

    query = m.text.split(maxsplit=1)[1].strip()
    msg = await m.reply("Fetching stream info...")
    info = await asyncio.to_thread(ytdl_extract, query, video)
    if not info:
        await msg.edit("Failed to fetch media information.")
        return None

    stream_url = info.get("url")
    if stream_url:
        command = build_ffmpeg_network(stream_url, rtmp_url, video)
    else:
        requested = info.get("requested_formats") or []
        video_url = next((f.get("url") for f in requested if f.get("vcodec") not in (None, "none") and f.get("url")), None)
        audio_url = next((f.get("url") for f in requested if f.get("acodec") not in (None, "none") and f.get("url")), None)
        if not video_url or not audio_url:
            await msg.edit("No playable stream URL was returned by yt-dlp.")
            return None
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-re",
            "-i",
            video_url,
            "-re",
            "-i",
            audio_url,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-tune",
            "zerolatency",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
            "-r",
            "30",
            "-g",
            "60",
            "-b:v",
            "2000k",
            "-maxrate",
            "2200k",
            "-bufsize",
            "4000k",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-ac",
            "2",
            "-ar",
            "44100",
            "-flvflags",
            "no_duration_filesize",
            "-f",
            "flv",
            rtmp_url,
        ]

    title = info.get("title") or "Unknown"
    duration = format_duration(info.get("duration", 0))
    return {
        "chat_id": m.chat.id,
        "title": title,
        "duration": duration,
        "caption": f"Streaming{' (Audio)' if not video else ''}: {title}\nDuration: {duration}",
        "msg": msg,
        "ffmpeg_cmd": command,
        "user_id": m.from_user.id if m.from_user else 0,
        "username": m.from_user.username if m.from_user and m.from_user.username else "unknown",
        "stream_type": "YTPLAY" if video else "YTAUDIO",
    }


@bot.on_message(filters.command("ytplay"))
async def ytplay(_, m: Message):
    item = await create_ytdlp_item(m, video=True)
    if not item:
        return
    enqueue_item(item)
    await item["msg"].edit(f"Queued: {item['title']}")
    if m.from_user:
        await send_log(m.from_user.id, m.from_user.username or "unknown", m.chat.id, "YTPLAY", item["title"], item["duration"])


@bot.on_message(filters.command("ytaudio"))
async def ytaudio(_, m: Message):
    item = await create_ytdlp_item(m, video=False)
    if not item:
        return
    enqueue_item(item)
    await item["msg"].edit(f"Queued: {item['title']}")
    if m.from_user:
        await send_log(m.from_user.id, m.from_user.username or "unknown", m.chat.id, "YTAUDIO", item["title"], item["duration"])


@bot.on_message(filters.command("help"))
async def help_cmd(_, m: Message):
    await m.reply(
        "RTMP Streaming Help\n\nUse the categories below to find commands.",
        reply_markup=build_home_keyboard(),
    )


if __name__ == "__main__":
    required = {
        "API_ID": API_ID,
        "API_HASH": API_HASH,
        "BOT_TOKEN": BOT_TOKEN,
        "DEFAULT_RTMP_URL": DEFAULT_RTMP_URL,
        "MONGO_URL": MONGO_URL,
        "OWNER_ID": OWNER_ID,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise SystemExit(f"Missing configuration: {', '.join(missing)}")
    bot.run()
