from __future__ import annotations

from datetime import datetime
from typing import Any

from pymongo import MongoClient


class Database:
    def __init__(self, mongo_url: str):
        self.enabled = bool(mongo_url)
        if not self.enabled:
            self.client = None
            self.db = None
            return

        self.client = MongoClient(mongo_url)
        self.db = self.client["satoru_gojo"]
        self.users = self.db["users"]
        self.rtmp = self.db["rtmp_keys"]
        self.history = self.db["stream_history"]
        self.users.create_index("user_id", unique=True)
        self.rtmp.create_index("chat_id", unique=True)
        self.history.create_index("timestamp")

    async def add_user(self, user_id: int, username: str | None) -> None:
        if not self.enabled:
            return
        self.users.update_one(
            {"user_id": user_id},
            {
                "$set": {"username": username or "", "last_seen": datetime.utcnow()},
                "$setOnInsert": {"joined_at": datetime.utcnow()},
            },
            upsert=True,
        )

    async def set_rtmp_key(self, chat_id: int, key: str, by_user: int) -> None:
        if not self.enabled:
            return
        self.rtmp.update_one(
            {"chat_id": chat_id},
            {
                "$set": {
                    "chat_id": chat_id,
                    "key": key,
                    "updated_by": by_user,
                    "updated_at": datetime.utcnow(),
                }
            },
            upsert=True,
        )

    async def get_rtmp_key(self, chat_id: int) -> str | None:
        if not self.enabled:
            return None
        doc = self.rtmp.find_one({"chat_id": chat_id})
        return doc.get("key") if doc else None

    async def add_stream_history(self, payload: dict[str, Any]) -> None:
        if not self.enabled:
            return
        payload["timestamp"] = datetime.utcnow()
        self.history.insert_one(payload)
