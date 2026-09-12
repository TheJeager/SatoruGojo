import base64
import os
import tempfile

from dotenv import load_dotenv

load_dotenv()

OWNER_ID = int(os.getenv("OWNER_ID", "0"))
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DEFAULT_RTMP_URL = os.getenv("DEFAULT_RTMP_URL", "rtmps://dc5-1.rtmp.t.me/s/")
LOGGER_ID = int(os.getenv("LOGGER_ID", "0"))
MONGO_URL = os.getenv("MONGO_URL", "")
YTDLP_PROXY = os.getenv("YTDLP_PROXY", "").strip()


def _prepare_cookie_file() -> str:
    encoded = os.getenv("YTDLP_COOKIES_B64", "").strip()
    if encoded:
        try:
            data = base64.b64decode(encoded, validate=True)
            if b"# Netscape HTTP Cookie File" in data[:512]:
                path = os.path.join(tempfile.gettempdir(), "gojo_ytdlp_cookies.txt")
                with open(path, "wb") as file:
                    file.write(data)
                try:
                    os.chmod(path, 0o600)
                except OSError:
                    pass
                return path
        except Exception:
            pass

    path = os.getenv("YTDLP_COOKIE_FILE", "/app/cookies.txt").strip()
    if not path or not os.path.isfile(path):
        return ""

    try:
        with open(path, "rb") as file:
            header = file.read(512)
        if b"# Netscape HTTP Cookie File" not in header and b"# HTTP Cookie File" not in header:
            return ""
    except OSError:
        return ""

    return path


YTDLP_COOKIE_FILE = _prepare_cookie_file()
