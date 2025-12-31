from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
import os
from dotenv import load_dotenv
from models.user import UserModel
from asyncio.log import logger

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

class Database:
    client: AsyncIOMotorClient = None

db = Database()

async def init_db():
    db.client = AsyncIOMotorClient(MONGO_URI)
    database = db.client["voicebot"]
    
    await init_beanie(
        database=database, 
        document_models=[
            UserModel
        ]
    )
    
    logger.debug("Database connected successfully")

def get_database() -> AsyncIOMotorClient:
    return db.client

async def close_db():
    if db.client:
        db.client.close()