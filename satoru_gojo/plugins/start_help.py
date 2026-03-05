from pyrogram import Client, filters
from pyrogram.types import Message

from satoru_gojo.config import settings


@Client.on_message(filters.command(["start", "help"]) & filters.private)
async def start_help(_: Client, message: Message) -> None:
    text = (
        "**Satoru Gojo Stream Bot v2**\n\n"
        "Commands:\n"
        "/setrtmp <key> - Save Telegram RTMP stream key\n"
        "/stream <url or search> - Start yt-dlp powered stream\n"
        "/radio <station> - Start 24x7 live radio stream\n"
        "/radio_list - Show built-in station presets\n"
        "/stop - Stop running stream\n"
        "/status - Show active stream status\n\n"
        f"Owner: `{settings.owner_id or 'not set'}`"
    )
    await message.reply_text(text)
