from satoru_gojo.config import settings
from satoru_gojo.database import Database
from satoru_gojo.services import StreamManager

db = Database(settings.mongo_url)
manager = StreamManager(db)
