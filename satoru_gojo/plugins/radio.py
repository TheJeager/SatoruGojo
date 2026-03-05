from pyrogram import Client, filters
from pyrogram.types import Message

from satoru_gojo.main_context import manager


@Client.on_message(filters.command("radio_list") & filters.group)
async def radio_list(_: Client, message: Message) -> None:
    stations = "\n".join(f"- `{name}`" for name in sorted(manager.radio_presets))
    await message.reply_text(f"Available 24x7 radio stations:\n{stations}")


@Client.on_message(filters.command("radio") & filters.group)
async def radio(_: Client, message: Message) -> None:
    if len(message.command) < 2:
        await message.reply_text("Usage: /radio <station> (use /radio_list)")
        return

    station = message.command[1]
    progress = await message.reply_text("Starting radio playback...")
    try:
        title = await manager.start_radio(message.chat.id, station, message.from_user.id if message.from_user else 0)
        await progress.edit_text(f"Live radio started: **{title}**")
    except Exception as exc:
        await progress.edit_text(f"Failed to start radio:\n`{exc}`")
