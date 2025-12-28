import os
import time
import threading
import subprocess
import logging
import asyncio
import tempfile
from collections import defaultdict, deque
from typing import Optional, List, Dict, Tuple
from datetime import datetime

import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

try:
    from config import (
        OWNER_ID,
        API_ID,
        API_HASH,
        BOT_TOKEN,
        DEFAULT_RTMP_URL,
        LOGGER_ID,
        MONGO_URL
    )
except ImportError:
    OWNER_ID = int(os.getenv("OWNER_ID", 0))
    API_ID = int(os.getenv("API_ID", 0))
    API_HASH = os.getenv("API_HASH", "")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    DEFAULT_RTMP_URL = os.getenv("DEFAULT_RTMP_URL", "")
    LOGGER_ID = int(os.getenv("LOGGER_ID", 0))
    MONGO_URL = os.getenv("MONGO_URL", "")

from database import Database

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("GojoSatoru")
file_handler = logging.FileHandler("stream.log", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
file_handler.setLevel(logging.WARNING)
logger.addHandler(file_handler)

bot = Client("RTMPBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
db = Database(MONGO_URL)

rtmp_keys: Dict[int, str] = {}
ffmpeg_processes: Dict[int, Optional[subprocess.Popen]] = {}
queues = defaultdict(deque)
queue_locks = defaultdict(threading.Lock)
stream_status: Dict[int, str] = {}

YTDL_OPTS_WITH_COOKIES = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "cookiefile": "cookies.txt",
    "socket_timeout": 30,
}

YTDL_OPTS_NO_COOKIES = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "socket_timeout": 30,
}

def build_ffmpeg_video(input_file: str, rtmp_url: str) -> List[str]:
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-fflags", "nobuffer", "-flags", "low_delay",
        "-probesize", "32", "-analyzeduration", "0",
        "-re", "-i", input_file,
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
        "-pix_fmt", "yuv420p", "-b:v", "2000k", "-maxrate", "2000k", "-bufsize", "4000k",
        "-g", "30", "-keyint_min", "30",
        "-vf", "scale=1280:720,fps=30",
        "-c:a", "aac", "-b:a", "128k", "-ac", "2", "-ar", "44100",
        "-flvflags", "no_duration_filesize",
        "-f", "flv", rtmp_url
    ]

def build_ffmpeg_audio(audio_url: str, rtmp_url: str) -> List[str]:
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-fflags", "nobuffer", "-flags", "low_delay",
        "-probesize", "32", "-analyzeduration", "0",
        "-i", audio_url,
        "-vn", "-c:a", "aac", "-b:a", "128k", "-ac", "2", "-ar", "44100",
        "-flvflags", "no_duration_filesize",
        "-f", "flv", rtmp_url
    ]

def enqueue_rt(item: Dict) -> None:
    with queue_locks[item["chat_id"]]:
        queues[item["chat_id"]].append(item)

def get_rtmp_url(chat_id: int) -> Optional[str]:
    key = rtmp_keys.get(chat_id)
    return f"{DEFAULT_RTMP_URL.rstrip('/')}/{key}" if key else None

def stop_ffmpeg(chat_id: int) -> None:
    process = ffmpeg_processes.get(chat_id)
    if process:
        try:
            process.terminate()
            process.wait(timeout=5)
        except:
            try:
                process.kill()
            except:
                pass
    ffmpeg_processes[chat_id] = None
    stream_status[chat_id] = "stopped"

def format_duration(seconds: int) -> str:
    try:
        seconds = int(seconds or 0)
    except:
        seconds = 0
    mins, secs = divmod(seconds, 60)
    hours, mins = divmod(mins, 60)
    return f"{hours}:{mins:02}:{secs:02}" if hours else f"{mins}:{secs:02}"

def ytdl_extract_with_fallback(query: str, video: bool = True) -> Tuple[Optional[Dict], bool]:
    opts_with_cookies = YTDL_OPTS_WITH_COOKIES.copy()
    opts_with_cookies["format"] = "bestaudio/best" if not video else "bestvideo+bestaudio/best"
    
    try:
        with yt_dlp.YoutubeDL(opts_with_cookies) as ydl:
            info = ydl.extract_info(query, download=False)
            if "entries" in info and info["entries"]:
                info = info["entries"][0]
            return info, True
    except:
        pass
    
    opts_no_cookies = YTDL_OPTS_NO_COOKIES.copy()
    opts_no_cookies["format"] = "bestaudio/best" if not video else "bestvideo+bestaudio/best"
    
    try:
        with yt_dlp.YoutubeDL(opts_no_cookies) as ydl:
            info = ydl.extract_info(query, download=False)
            if "entries" in info and info["entries"]:
                info = info["entries"][0]
            return info, False
    except:
        return None, False

def run_ffmpeg(chat_id: int, cmd: List[str], input_file: Optional[str] = None, stream_data: Dict = None) -> None:
    try:
        stream_status[chat_id] = "streaming"
        start_time = time.time()
        process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        ffmpeg_processes[chat_id] = process
        
        while process.poll() is None:
            time.sleep(0.1)
        
        stream_status[chat_id] = "completed"
        duration = time.time() - start_time
        
        if stream_data:
            asyncio.run(db.add_stream_stat(
                user_id=stream_data.get("user_id"),
                username=stream_data.get("username"),
                title=stream_data.get("title"),
                duration=duration,
                stream_type=stream_data.get("stream_type"),
                status="completed"
            ))
    except Exception as e:
        logger.error(f"FFmpeg error chat {chat_id}: {e}")
        stream_status[chat_id] = "error"
        if stream_data:
            asyncio.run(db.add_stream_stat(
                user_id=stream_data.get("user_id"),
                username=stream_data.get("username"),
                title=stream_data.get("title"),
                duration=0,
                stream_type=stream_data.get("stream_type"),
                status="error"
            ))
    finally:
        ffmpeg_processes[chat_id] = None
        if input_file and os.path.exists(input_file):
            try:
                os.unlink(input_file)
            except:
                pass
        asyncio.run(start_next_in_queue(chat_id))

async def start_next_in_queue(chat_id: int) -> None:
    with queue_locks[chat_id]:
        if not queues[chat_id]:
            return
        item = queues[chat_id].popleft()
    
    url = get_rtmp_url(chat_id)
    if not url:
        try:
            await item["msg"].edit("No RTMP key configured.")
        except:
            pass
        return
    
    try:
        if item.get("thumbnail"):
            await item["msg"].reply_photo(item["thumbnail"], caption=item["caption"])
        else:
            await item["msg"].edit(item["caption"])
    except:
        try:
            await item["msg"].edit(item["caption"])
        except:
            pass
    
    stop_ffmpeg(chat_id)
    
    if "audio_url" in item:
        cmd = build_ffmpeg_audio(item["audio_url"], url)
    else:
        cmd = item["ffmpeg_cmd"]
    
    stream_data = {
        "user_id": item.get("user_id"),
        "username": item.get("username"),
        "title": item.get("title"),
        "stream_type": item.get("stream_type")
    }
    
    threading.Thread(target=run_ffmpeg, args=(chat_id, cmd, item.get("input_file"), stream_data), daemon=True).start()

async def send_log(user_id: int, username: str, chat_id: int, action: str, title: str = "", duration: str = "") -> None:
    if not LOGGER_ID or LOGGER_ID == 0:
        return
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_text = f"[{action}]\nUser: @{username} (ID: {user_id})\nChat: {chat_id}"
    
    if title:
        log_text += f"\nTitle: {title}"
    if duration:
        log_text += f"\nDuration: {duration}"
    
    log_text += f"\nTime: {timestamp}"
    
    try:
        await bot.send_message(LOGGER_ID, log_text)
    except Exception as e:
        logger.error(f"Log send error: {e}")

def is_admin(user_id: int) -> bool:
    return user_id == OWNER_ID

@bot.on_message(filters.command("start"))
async def start(_, m: Message):
    await db.add_user(m.from_user.id, m.from_user.username or "unknown")
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Commands", callback_data="cmds")],
        [
            InlineKeyboardButton("Support", url="https://t.me/RadhaSprt"),
            InlineKeyboardButton("Updates", url="https://t.me/CodingAssociation")
        ]
    ])
    
    text = f"""Hey @{m.from_user.username}

I'm Gojo Satoru, a RTMP Telegram streaming bot with faster playback.

FEATURES:
- Ultra-low latency streaming
- Queue-based media management
- YouTube & direct URL support
- Optimized FFmpeg encoding
- Fast video/audio extraction

Start streaming with /help or /setkey"""
    
    try:
        await m.reply_photo(
            photo="https://i.ibb.co/QFt3Z9bC/tmpg1y9wbs8.jpg",
            caption=text,
            reply_markup=buttons
        )
    except:
        await m.reply(text, reply_markup=buttons)

@bot.on_callback_query(filters.regex("cmds"))
async def show_commands(_, query: CallbackQuery):
    commands_text = """COMMANDS:

/setkey <key> - Set RTMP stream key
/play - Reply with media (video+audio)
/playaudio - Reply with media (audio only)
/uplay <url> - Stream direct URL
/ytplay <query> - Stream YouTube (video)
/ytaudio <query> - Stream YouTube (audio)
/stop - Stop stream and clear queue
/skip - Skip current stream
/queue - Show queue list
/ping - Check latency
/status - Stream status
/stats - Your stream statistics
/broadcast <msg> - Broadcast message (admin only)"""
    
    back = InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back")]])
    await query.message.edit_text(commands_text, reply_markup=back)

@bot.on_callback_query(filters.regex("back"))
async def back(_, query: CallbackQuery):
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Commands", callback_data="cmds")],
        [
            InlineKeyboardButton("Support", url="https://t.me/RadhaSprt"),
            InlineKeyboardButton("Updates", url="https://t.me/CodingAssociation")
        ]
    ])
    
    text = f"""Hey @{query.from_user.username}

I'm Gojo Satoru, a RTMP Telegram streaming bot with faster playback.

FEATURES:
- Ultra-low latency streaming
- Queue-based media management
- YouTube & direct URL support
- Optimized FFmpeg encoding
- Fast video/audio extraction

Start streaming with /help or /setkey"""
    
    try:
        await query.message.edit_caption(caption=text, reply_markup=buttons)
    except:
        try:
            await query.message.edit_text(text, reply_markup=buttons)
        except:
            pass

@bot.on_message(filters.command("setkey"))
async def setkey(_, m: Message):
    if not is_admin(m.from_user.id):
        return await m.reply("Unauthorized.")
    
    if len(m.command) < 2:
        return await m.reply("Usage: /setkey <RTMP_KEY>")
    
    rtmp_keys[m.chat.id] = m.command[1]
    await m.reply("RTMP key configured.")
    await send_log(m.from_user.id, m.from_user.username or "unknown", m.chat.id, "SETKEY")

@bot.on_message(filters.command("ping"))
async def ping(_, m: Message):
    start = time.perf_counter()
    reply = await m.reply("Measuring latency...")
    end = time.perf_counter()
    latency = int((end - start) * 1000)
    await reply.edit_text(f"Latency: {latency}ms")

@bot.on_message(filters.command("status"))
async def status(_, m: Message):
    st = stream_status.get(m.chat.id, "idle")
    await m.reply(f"Stream status: {st}")

@bot.on_message(filters.command("stats"))
async def stats(_, m: Message):
    user_stats = await db.get_user_stats(m.from_user.id)
    
    text = "Stream Statistics\n\n"
    text += f"Total Streams: {user_stats.get('total_streams', 0)}\n"
    text += f"Successful Streams: {user_stats.get('successful_streams', 0)}\n"
    text += f"Failed Streams: {user_stats.get('failed_streams', 0)}\n"
    text += f"Total Stream Time: {int(user_stats.get('total_duration', 0))} seconds\n"
    text += f"Average Stream Time: {int(user_stats.get('avg_duration', 0))} seconds"
    
    await m.reply(text)

@bot.on_message(filters.command("stop"))
async def stop(_, m: Message):
    stop_ffmpeg(m.chat.id)
    queues[m.chat.id].clear()
    await m.reply("Stream stopped.")
    await send_log(m.from_user.id, m.from_user.username or "unknown", m.chat.id, "STOP")

@bot.on_message(filters.command("skip"))
async def skip(_, m: Message):
    stop_ffmpeg(m.chat.id)
    await m.reply("Stream skipped.")
    await send_log(m.from_user.id, m.from_user.username or "unknown", m.chat.id, "SKIP")
    await start_next_in_queue(m.chat.id)

@bot.on_message(filters.command("queue"))
async def show_queue(_, m: Message):
    q = queues[m.chat.id]
    if not q:
        return await m.reply("Queue is empty.")
    
    lines = ["QUEUE:"]
    for idx, item in enumerate(q, 1):
        lines.append(f"{idx}. {item['title']} ({item['duration']})")
    
    await m.reply("\n".join(lines))

@bot.on_message(filters.command("broadcast"))
async def broadcast(_, m: Message):
    if not is_admin(m.from_user.id):
        return await m.reply("Unauthorized.")
    
    if len(m.command) < 2:
        return await m.reply("Usage: /broadcast <message>")
    
    message = m.text.split(maxsplit=1)[1]
    users = await db.get_all_users()
    
    sent = 0
    for user in users:
        try:
            await bot.send_message(user['user_id'], message)
            sent += 1
        except:
            pass
    
    await m.reply(f"Broadcast sent to {sent} users.")
    await db.add_broadcast(m.from_user.id, message, sent)

@bot.on_message(filters.command("play"))
async def play(_, m: Message):
    if not m.reply_to_message or not (m.reply_to_message.audio or m.reply_to_message.voice or m.reply_to_message.video):
        return await m.reply("Reply with audio or video file.")
    
    url = get_rtmp_url(m.chat.id)
    if not url:
        return await m.reply("Set RTMP key first using /setkey.")
    
    msg = await m.reply("Processing...")
    
    try:
        suffix = m.reply_to_message.file.file_name.split('.')[-1] if hasattr(m.reply_to_message, 'file') and m.reply_to_message.file else "tmp"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{suffix}') as f:
            await m.reply_to_message.download(file_name=f.name)
            filepath = f.name
        
        title = getattr(m.reply_to_message, "file_name", "Media")
        duration = format_duration(getattr(m.reply_to_message, "duration", 0))
        
        caption = f"Streaming: {title}\nDuration: {duration}"
        
        item = {
            "chat_id": m.chat.id,
            "title": title,
            "duration": duration,
            "caption": caption,
            "thumbnail": None,
            "msg": msg,
            "input_file": filepath,
            "ffmpeg_cmd": build_ffmpeg_video(filepath, url),
            "user_id": m.from_user.id,
            "username": m.from_user.username or "unknown",
            "stream_type": "PLAY"
        }
        
        enqueue_rt(item)
        await msg.edit(f"Queued: {title}")
        await send_log(m.from_user.id, m.from_user.username or "unknown", m.chat.id, "PLAY", title, duration)
        
        if not ffmpeg_processes.get(m.chat.id):
            await start_next_in_queue(m.chat.id)
    
    except Exception as e:
        await msg.edit(f"Error: {str(e)[:50]}")
        logger.error(f"Play error: {e}")

@bot.on_message(filters.command("playaudio"))
async def playaudio(_, m: Message):
    if not m.reply_to_message or not (m.reply_to_message.audio or m.reply_to_message.voice or m.reply_to_message.video):
        return await m.reply("Reply with audio or video file.")
    
    url = get_rtmp_url(m.chat.id)
    if not url:
        return await m.reply("Set RTMP key first using /setkey.")
    
    msg = await m.reply("Processing...")
    
    try:
        suffix = m.reply_to_message.file.file_name.split('.')[-1] if hasattr(m.reply_to_message, 'file') and m.reply_to_message.file else "tmp"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{suffix}') as f:
            await m.reply_to_message.download(file_name=f.name)
            filepath = f.name
        
        title = getattr(m.reply_to_message, "file_name", "Media")
        duration = format_duration(getattr(m.reply_to_message, "duration", 0))
        
        caption = f"Streaming (Audio): {title}\nDuration: {duration}"
        
        item = {
            "chat_id": m.chat.id,
            "title": title,
            "duration": duration,
            "caption": caption,
            "thumbnail": None,
            "msg": msg,
            "input_file": filepath,
            "ffmpeg_cmd": build_ffmpeg_audio(filepath, url),
            "user_id": m.from_user.id,
            "username": m.from_user.username or "unknown",
            "stream_type": "PLAYAUDIO"
        }
        
        enqueue_rt(item)
        await msg.edit(f"Queued: {title}")
        await send_log(m.from_user.id, m.from_user.username or "unknown", m.chat.id, "PLAYAUDIO", title, duration)
        
        if not ffmpeg_processes.get(m.chat.id):
            await start_next_in_queue(m.chat.id)
    
    except Exception as e:
        await msg.edit(f"Error: {str(e)[:50]}")
        logger.error(f"Playaudio error: {e}")

@bot.on_message(filters.command("uplay"))
async def uplay(_, m: Message):
    if len(m.command) < 2:
        return await m.reply("Usage: /uplay <url>")
    
    url = get_rtmp_url(m.chat.id)
    if not url:
        return await m.reply("Set RTMP key first using /setkey.")
    
    media_url = m.text.split(maxsplit=1)[1]
    
    item = {
        "chat_id": m.chat.id,
        "title": "Direct URL",
        "duration": "Unknown",
        "caption": "Streaming from URL",
        "thumbnail": None,
        "msg": await m.reply("Queued: Direct URL"),
        "ffmpeg_cmd": build_ffmpeg_video(media_url, url),
        "user_id": m.from_user.id,
        "username": m.from_user.username or "unknown",
        "stream_type": "UPLAY"
    }
    
    enqueue_rt(item)
    await send_log(m.from_user.id, m.from_user.username or "unknown", m.chat.id, "UPLAY")
    
    if not ffmpeg_processes.get(m.chat.id):
        await start_next_in_queue(m.chat.id)

@bot.on_message(filters.command("ytplay"))
async def ytplay(_, m: Message):
    if len(m.command) < 2:
        return await m.reply("Usage: /ytplay <query>")
    
    url = get_rtmp_url(m.chat.id)
    if not url:
        return await m.reply("Set RTMP key first using /setkey.")
    
    query = m.text.split(maxsplit=1)[1]
    msg = await m.reply("Fetching stream info...")
    
    try:
        loop = asyncio.get_event_loop()
        info, used_cookies = await loop.run_in_executor(None, lambda: ytdl_extract_with_fallback(query, video=True))
        
        if not info:
            return await msg.edit("Failed to fetch stream.")
        
        stream_url = info.get("url") or (info.get("formats", [{}])[-1].get("url") if info.get("formats") else None)
        
        if not stream_url:
            return await msg.edit("No playable stream found.")
        
        title = info.get("title", "Unknown")
        duration = format_duration(info.get("duration", 0))
        
        item = {
            "chat_id": m.chat.id,
            "title": title,
            "duration": duration,
            "caption": f"Streaming: {title}\nDuration: {duration}",
            "thumbnail": None,
            "msg": msg,
            "audio_url": stream_url,
            "ffmpeg_cmd": build_ffmpeg_video(stream_url, url),
            "user_id": m.from_user.id,
            "username": m.from_user.username or "unknown",
            "stream_type": "YTPLAY"
        }
        
        enqueue_rt(item)
        await msg.edit(f"Queued: {title}")
        await send_log(m.from_user.id, m.from_user.username or "unknown", m.chat.id, "YTPLAY", title, duration)
        
        if not ffmpeg_processes.get(m.chat.id):
            await start_next_in_queue(m.chat.id)
    
    except Exception as e:
        await msg.edit(f"Error: {str(e)[:50]}")
        logger.error(f"YT Play error: {e}")

@bot.on_message(filters.command("ytaudio"))
async def ytaudio(_, m: Message):
    if len(m.command) < 2:
        return await m.reply("Usage: /ytaudio <query>")
    
    url = get_rtmp_url(m.chat.id)
    if not url:
        return await m.reply("Set RTMP key first using /setkey.")
    
    query = m.text.split(maxsplit=1)[1]
    msg = await m.reply("Fetching audio stream info...")
    
    try:
        loop = asyncio.get_event_loop()
        info, used_cookies = await loop.run_in_executor(None, lambda: ytdl_extract_with_fallback(query, video=False))
        
        if not info:
            return await msg.edit("Failed to fetch stream.")
        
        stream_url = info.get("url") or (info.get("formats", [{}])[-1].get("url") if info.get("formats") else None)
        
        if not stream_url:
            return await msg.edit("No playable stream found.")
        
        title = info.get("title", "Unknown")
        duration = format_duration(info.get("duration", 0))
        
        item = {
            "chat_id": m.chat.id,
            "title": title,
            "duration": duration,
            "caption": f"Streaming (Audio): {title}\nDuration: {duration}",
            "thumbnail": None,
            "msg": msg,
            "audio_url": stream_url,
            "ffmpeg_cmd": build_ffmpeg_audio(stream_url, url),
            "user_id": m.from_user.id,
            "username": m.from_user.username or "unknown",
            "stream_type": "YTAUDIO"
        }
        
        enqueue_rt(item)
        await msg.edit(f"Queued: {title}")
        await send_log(m.from_user.id, m.from_user.username or "unknown", m.chat.id, "YTAUDIO", title, duration)
        
        if not ffmpeg_processes.get(m.chat.id):
            await start_next_in_queue(m.chat.id)
    
    except Exception as e:
        await msg.edit(f"Error: {str(e)[:50]}")
        logger.error(f"YT Audio error: {e}")

@bot.on_message(filters.command("help"))
async def help_cmd(_, m: Message):
    help_text = """Help - RTMP Streaming Bot

BASIC COMMANDS:
/start - Start the bot
/setkey <key> - Set your RTMP stream key
/help - Show this help message

STREAMING COMMANDS:
/play - Stream Telegram media (video+audio)
/playaudio - Stream Telegram media (audio only)
/uplay <url> - Stream direct URL
/ytplay <query> - Stream YouTube video
/ytaudio <query> - Stream YouTube audio only

CONTROL COMMANDS:
/stop - Stop current stream
/skip - Skip to next in queue
/queue - View queue list

INFO COMMANDS:
/status - Check stream status
/stats - View your statistics
/ping - Check bot latency

ADMIN COMMANDS:
/broadcast <msg> - Send message to all users"""
    
    await m.reply(help_text)

if __name__ == "__main__":
    if not all([API_ID, API_HASH, BOT_TOKEN, DEFAULT_RTMP_URL, MONGO_URL]):
        print("Missing configuration. Please set all required variables.")
        exit(1)
    
    bot.run()