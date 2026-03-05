from pyrogram import Client, filters
from pyrogram.types import Message

from satoru_gojo.main_context import manager


@Client.on_message(filters.command("setrtmp") & filters.group)
async def set_rtmp(_: Client, message: Message) -> None:
    if len(message.command) < 2:
        await message.reply_text("Usage: /setrtmp <stream_key>")
        return
    key = message.command[1].strip()
    rtmp = await manager.set_rtmp_key(message.chat.id, key, message.from_user.id if message.from_user else 0)
    await message.reply_text(f"RTMP key saved. Full endpoint:\n`{rtmp}`")


@Client.on_message(filters.command("stream") & filters.group)
async def stream(_: Client, message: Message) -> None:
    if len(message.command) < 2:
        await message.reply_text("Usage: /stream <youtube-url or search query>")
        return

    query = message.text.split(maxsplit=1)[1]
    status = await message.reply_text("Resolving stream with yt-dlp and starting ffmpeg...")
    try:
        title = await manager.start_stream(message.chat.id, query, message.from_user.id if message.from_user else 0)
        await status.edit_text(f"Started streaming: **{title}**")
    except Exception as exc:
        await status.edit_text(f"Failed to start stream:\n`{exc}`")


@Client.on_message(filters.command("stop") & filters.group)
async def stop(_: Client, message: Message) -> None:
    stopped = await manager.stop_stream(message.chat.id)
    await message.reply_text("Stopped active stream." if stopped else "No running stream.")


@Client.on_message(filters.command("status") & filters.group)
async def status(_: Client, message: Message) -> None:
    await message.reply_text(manager.status(message.chat.id))
