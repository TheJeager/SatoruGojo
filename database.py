from pymongo import MongoClient
from datetime import datetime
from typing import Dict, List, Optional

class Database:
    def __init__(self, mongo_url: str):
        self.client = MongoClient(mongo_url)
        self.db = self.client["GojoSatoru"]
        self.users = self.db["users"]
        self.streams = self.db["streams"]
        self.broadcasts = self.db["broadcasts"]
        
        self.users.create_index("user_id", unique=True)
        self.streams.create_index("user_id")
        self.broadcasts.create_index("timestamp")
    
    async def add_user(self, user_id: int, username: str) -> None:
        try:
            self.users.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "username": username,
                        "last_seen": datetime.now()
                    },
                    "$setOnInsert": {
                        "user_id": user_id,
                        "joined_at": datetime.now()
                    }
                },
                upsert=True
            )
        except Exception as e:
            print(f"Error adding user: {e}")
    
    async def add_stream_stat(self, user_id: int, username: str, title: str, duration: float, stream_type: str, status: str) -> None:
        try:
            self.streams.insert_one({
                "user_id": user_id,
                "username": username,
                "title": title,
                "duration": duration,
                "stream_type": stream_type,
                "status": status,
                "timestamp": datetime.now()
            })
        except Exception as e:
            print(f"Error adding stream stat: {e}")
    
    async def get_user_stats(self, user_id: int) -> Dict:
        try:
            streams = list(self.streams.find({"user_id": user_id}))
            
            total_streams = len(streams)
            successful_streams = len([s for s in streams if s["status"] == "completed"])
            failed_streams = len([s for s in streams if s["status"] == "error"])
            total_duration = sum(s.get("duration", 0) for s in streams)
            avg_duration = total_duration / successful_streams if successful_streams > 0 else 0
            
            return {
                "user_id": user_id,
                "total_streams": total_streams,
                "successful_streams": successful_streams,
                "failed_streams": failed_streams,
                "total_duration": total_duration,
                "avg_duration": avg_duration
            }
        except Exception as e:
            print(f"Error getting user stats: {e}")
            return {
                "total_streams": 0,
                "successful_streams": 0,
                "failed_streams": 0,
                "total_duration": 0,
                "avg_duration": 0
            }
    
    async def get_all_users(self) -> List[Dict]:
        try:
            return list(self.users.find({}, {"_id": 0}))
        except Exception as e:
            print(f"Error getting all users: {e}")
            return []
    
    async def add_broadcast(self, admin_id: int, message: str, sent_to: int) -> None:
        try:
            self.broadcasts.insert_one({
                "admin_id": admin_id,
                "message": message,
                "sent_to": sent_to,
                "timestamp": datetime.now()
            })
        except Exception as e:
            print(f"Error adding broadcast: {e}")
    
    async def get_stream_stats_by_type(self, user_id: int, stream_type: str) -> int:
        try:
            count = self.streams.count_documents({"user_id": user_id, "stream_type": stream_type})
            return count
        except Exception as e:
            print(f"Error getting stream stats by type: {e}")
            return 0
    
    async def get_total_broadcasts(self) -> int:
        try:
            return self.broadcasts.count_documents({})
        except Exception as e:
            print(f"Error getting total broadcasts: {e}")
            return 0
    
    async def get_total_users(self) -> int:
        try:
            return self.users.count_documents({})
        except Exception as e:
            print(f"Error getting total users: {e}")
            return 0
    
    async def get_total_streams(self) -> int:
        try:
            return self.streams.count_documents({})
        except Exception as e:
            print(f"Error getting total streams: {e}")
            return 0
    
    async def get_recent_streams(self, limit: int = 10) -> List[Dict]:
        try:
            return list(self.streams.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit))
        except Exception as e:
            print(f"Error getting recent streams: {e}")
            return []
    
    async def delete_user(self, user_id: int) -> None:
        try:
            self.users.delete_one({"user_id": user_id})
            self.streams.delete_many({"user_id": user_id})
        except Exception as e:
            print(f"Error deleting user: {e}")
    
    async def get_user_info(self, user_id: int) -> Optional[Dict]:
        try:
            return self.users.find_one({"user_id": user_id}, {"_id": 0})
        except Exception as e:
            print(f"Error getting user info: {e}")
            return None