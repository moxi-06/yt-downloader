from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI

client = AsyncIOMotorClient(MONGO_URI) if MONGO_URI else None
db = client.get_default_database() if client else None
users = db.users if db else None

async def add_user(user_id: int, username: str | None):
    if users is None:
        return
    await users.update_one({'_id': user_id}, {'$set': {'username': username}}, upsert=True)

async def list_user_ids():
    if users is None:
        return []
    cursor = users.find({}, {'_id': 1})
    return [doc['_id'] async for doc in cursor]

async def count_users():
    if users is None:
        return 0
    return await users.count_documents({})
