# SatoruGojo v2 - Telegram RTMP Streaming Bot

A fully restructured Telegram bot focused on:

- Stable **yt-dlp URL extraction** (with cookies support)
- **24x7 live radio playback** presets
- Low-latency FFmpeg pipeline for Telegram RTMP live streams
- Modular architecture (`plugins`, `services`, `database`, `utils`)

## New Project Structure

```text
SatoruGojo/
├── main.py
├── requirements.txt
├── config.py                    # backward-compatible exports
└── satoru_gojo/
    ├── bot.py                   # pyrogram app factory
    ├── config.py                # env/config loader + validation
    ├── main_context.py          # singleton DB + StreamManager
    ├── plugins/
    │   ├── start_help.py        # /start /help
    │   ├── stream.py            # /setrtmp /stream /stop /status
    │   └── radio.py             # /radio /radio_list
    ├── services/
    │   └── stream_manager.py    # core stream lifecycle management
    ├── database/
    │   └── mongo.py             # MongoDB persistence
    └── utils/
        ├── ytdlp.py             # fixed resilient extractor wrapper
        ├── ffmpeg.py            # low-latency command builder
        └── logger.py            # logging setup
```

## Commands

- `/setrtmp <stream_key>` Save stream key for this group/chat
- `/stream <url or query>` Start stream using yt-dlp + ffmpeg
- `/radio <station>` Start 24x7 radio preset
- `/radio_list` Show available radio stations
- `/stop` Stop live stream
- `/status` Get current stream status

## Required Environment Variables

- `API_ID`
- `API_HASH`
- `BOT_TOKEN`

Optional:

- `MONGO_URL`
- `OWNER_ID`
- `LOGGER_ID`
- `DEFAULT_RTMP_BASE` (default: `rtmps://dc5-1.rtmp.t.me/s/`)
- `COOKIES_PATH` (default: `cookies.txt`)
- `FFMPEG_BIN` (default: `ffmpeg`)

## Run

```bash
pip install -r requirements.txt
python main.py
```

## Notes

- Install FFmpeg and keep it available in `PATH`.
- For restricted YouTube sources, provide exported cookies in `cookies.txt`.
- Add the bot to a Telegram group and grant required streaming/admin permissions.
