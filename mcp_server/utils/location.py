import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
from dotenv import load_dotenv
from difflib import SequenceMatcher

# Load environment variables
load_dotenv(dotenv_path="/home/ubuntu/testing/mcp_server/.env")

# Config
MONGO_URI = os.getenv("MONGO_URI", os.getenv("MONGO_URI"))
DATABASE_NAME = os.getenv("DATABASE_NAME", "rakshak-ai")

# Setup connection
client = AsyncIOMotorClient(MONGO_URI)
db = client[DATABASE_NAME]

def similar(a, b):
    """Check similarity between two strings (0 to 1)"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

async def find_village_fuzzy(village_name, threshold=0.7):
    """Find village with fuzzy matching for spelling mistakes"""
    villages = db["villages"]
    
    # Get ALL villages first
    all_villages = await villages.find().to_list(length=None)
    
    # Find the best match
    best_match = None
    best_score = 0
    
    for village in all_villages:
        db_village_name = village.get("villagename", "")
        score = similar(village_name, db_village_name)
        
        if score > best_score:
            best_score = score
            best_match = village
    
    # Return if similarity is above threshold
    if best_score >= threshold:
        return best_match, best_score
    else:
        return None, best_score

async def get_station(station_id):
    """Get police station by ID"""
    piusers = db["piusers"]
    
    try:
        station = await piusers.find_one({"_id": ObjectId(station_id)})
        return station
    except:
        return None

async def search_village_fuzzy(village_name):
    """
    Search village with fuzzy matching for spelling errors
    
    Returns: (village_data, station_data, similarity_score)
    """
    if not village_name or not village_name.strip():
        return None, None, 0
    
    village_name = village_name.strip()
    
    # Try exact match first (fastest)
    villages = db["villages"]
    exact_match = await villages.find_one({
        "villagename": {"$regex": f"^{village_name}$", "$options": "i"}
    })
    
    if exact_match:
        station = await get_station(exact_match.get("stationId"))
        return exact_match, station, 1.0
    
    # If no exact match, try fuzzy search
    village, score = await find_village_fuzzy(village_name)
    
    if village:
        print(f"Found similar village: {village['villagename']} (Score: {score:.2f})")
        
        station = await get_station(village.get("stationId"))
        return village, station, score
    else:
        print(f"No village found for '{village_name}' (Best score: {score:.2f})")
        return None, None, score