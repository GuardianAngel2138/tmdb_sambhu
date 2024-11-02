from motor.motor_asyncio import AsyncIOMotorClient
import config
import datetime

# Initialize MongoDB client
mongo_client = AsyncIOMotorClient(config.MONGO_URI)
db = mongo_client['movie_bot_db']

async def store_activity_log(action, details):
    await db.activity_logs.insert_one({
        "action": action,
        "details": details,
        "timestamp": datetime.datetime.utcnow()
    })

async def get_recent_activities(limit=10):
    return await db.activity_logs.find().sort("timestamp", -1).limit(limit).to_list(length=limit)

# Define get_users function to fetch user details
async def get_users():
    return await db.users.find().to_list(length=100)
