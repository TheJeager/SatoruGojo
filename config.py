import os
from dotenv import load_dotenv

load_dotenv()

OWNER_ID = int(os.getenv("OWNER_ID", 0))
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DEFAULT_RTMP_URL = ("rtmps://dc5-1.rtmp.t.me/s/")
LOGGER_ID = int(os.getenv("LOGGER_ID", 0))
MONGO_URL = os.getenv("MONGO_URL", "")