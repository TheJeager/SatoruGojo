from datetime import datetime
from typing import Dict, List, Optional

from pymongo import MongoClient


class Database:
    def __init__(self, mongo_url: str):
        if not mongo_url:
            raise ValueError("MONGO_URL is required")
        self.client = MongoClient(mongo_url, serverSelectionTimeoutMS=10000)
        self.db = self.client["GojoSatoru"]
        self.users = self.db["users"]
        self.streams = self.db["streams"]
        self.broadcasts = self.db["broadcasts"]
        self.settings = self.db["settings"]
        self.users.create_index("user_id", unique=True)
        self.streams.create_index([("user_id", 1), ("timestamp", -1)])
        self.streams.create_index([("chat_id", 1), ("timestamp", -1)])
        self.broadcasts.create_index("timestamp")
        self.settings.create_index("chat_id", unique=True)
        self.client.admin.command("ping")

    async def add_user(self, user_id: int, username: str) -> None:
        now = datetime.utcnow()
        self.users.update_one(
            {"user_id": user_id},
            {
                "$set": {"username": username, "last_seen": now},
                "$setOnInsert": {"user_id": user_id, "joined_at": now},
            },
            upsert=True,
        )

    async def set_rtmp_key(self, chat_id: int, key: str) -> None:
        self.settings.update_one(
            {"chat_id": chat_id},
            {"$set": {"rtmp_key": key, "updated_at": datetime.utcnow()}},
            upsert=True,
        )

    async def get_rtmp_key(self, chat_id: int) -> Optional[str]:
        doc = self.settings.find_one({"chat_id": chat_id}, {"rtmp_key": 1})
        return doc.get("rtmp_key") if doc else None

    async def add_stream_stat(
        self,
        user_id: int,
        username: str,
        title: str,
        duration: float,
        stream_type: str,
        status: str,
        chat_id: Optional[int] = None,
    ) -> None:
        self.streams.insert_one(
            {
                "user_id": user_id,
                "username": username,
                "chat_id": chat_id,
                "title": title,
                "duration": float(duration or 0),
                "stream_type": stream_type,
                "status": status,
                "timestamp": datetime.utcnow(),
            }
        )

    async def get_user_stats(self, user_id: int) -> Dict:
        streams = list(self.streams.find({"user_id": user_id}, {"_id": 0}))
        total = len(streams)
        successful = sum(1 for item in streams if item.get("status") == "completed")
        failed = sum(1 for item in streams if item.get("status") == "error")
        total_duration = sum(float(item.get("duration", 0) or 0) for item in streams)
        avg_duration = total_duration / successful if successful else 0
        return {
            "user_id": user_id,
            "total_streams": total,
            "successful_streams": successful,
            "failed_streams": failed,
            "total_duration": total_duration,
            "avg_duration": avg_duration,
        }

    async def get_all_users(self) -> List[Dict]:
        return list(self.users.find({}, {"_id": 0}))

    async def add_broadcast(self, admin_id: int, message: str, sent_to: int) -> None:
        self.broadcasts.insert_one(
            {
                "admin_id": admin_id,
                "message": message,
                "sent_to": sent_to,
                "timestamp": datetime.utcnow(),
            }
        )

    async def get_stream_stats_by_type(self, user_id: int, stream_type: str) -> int:
        return self.streams.count_documents(
            {"user_id": user_id, "stream_type": stream_type}
        )

    async def get_total_broadcasts(self) -> int:
        return self.broadcasts.count_documents({})

    async def get_total_users(self) -> int:
        return self.users.count_documents({})

    async def get_total_streams(self) -> int:
        return self.streams.count_documents({})

    async def get_recent_streams(self, limit: int = 10) -> List[Dict]:
        return list(
            self.streams.find({}, {"_id": 0}).sort("timestamp", -1).limit(max(1, limit))
        )

    async def delete_user(self, user_id: int) -> None:
        self.users.delete_one({"user_id": user_id})
        self.streams.delete_many({"user_id": user_id})

    async def get_user_info(self, user_id: int) -> Optional[Dict]:
        return self.users.find_one({"user_id": user_id}, {"_id": 0})
