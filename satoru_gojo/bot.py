from pyrogram import Client

from satoru_gojo.config import settings, validate_settings
from satoru_gojo.utils.logger import setup_logging


def create_app() -> Client:
    validate_settings()
    setup_logging()
    return Client(
        "SatoruGojoBot",
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        bot_token=settings.bot_token,
        plugins={"root": "satoru_gojo.plugins"},
    )
