import os
import math
import redis
import json
import requests
from typing import Dict, List, Optional, Any
from openai import OpenAI
from pymongo import MongoClient
import logging
import re
# from dotenv import load_dotenv

# load_dotenv(dotenv_path="/home/ubuntu/voice-agent/src/.env")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# Initialize clients
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Initialize Redis with connection handling
redis_client = None
try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        password=os.getenv("REDIS_PASSWORD", ""),
        decode_responses=True,
        ssl=False,
        socket_connect_timeout=5,
        socket_timeout=5
    )
    redis_client.ping()
    logger.info("Redis connected successfully")
except (redis.ConnectionError, redis.AuthenticationError) as e:
    logger.warning(f"Redis connection failed: {e}")
    redis_client = None

# Initialize MongoDB
mongo_client = None
db = None
pi_users = None
sp_users = None

try:
    mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    mongo_client.admin.command('ping')
    mongo_client.admin.command('ping')
    db = mongo_client["rakshak-ai"]
    pi_users = db["piusers"]  # Use string access to be safe
    sp_users = db["spusers"]  # Use string access to be safe
    logger.info("MongoDB connected successfully")
    
    # Test collections exist
    pi_count = pi_users.count_documents({})
    sp_count = sp_users.count_documents({})
    logger.info(f"Found {pi_count} pi_users and {sp_count} sp_users in database")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    mongo_client = None
    db = None
    pi_users = None
    sp_users = None

# Cache constants
CACHE_TTL = 5 * 60  # 5 minutes in seconds
POLICE_STATIONS_CACHE_KEY = "police_station_names"

class LocationResult:
    def __init__(self, display_name: str, lat: float, lon: float, 
                 nearest_police_station: Dict[str, Any] = None):
        self.display_name = display_name
        self.lat = lat
        self.lon = lon
        self.nearest_police_station = nearest_police_station or {}

def location_selector(text_input: str, language: str = "english") -> Dict[str, Any]:
    """
    Main function to handle location selection based on text input
    """
    if text_input.strip() in ["0", "०"]:
        return {
            "message": "Policy message here",
            "next_state": "LANGUAGE_SELECTION",
            "is_template": "interactive"
        }

    location_name = text_input

    try:
        # Translate and process the location name
        try:
            location_name = translate_to_english(location_name)
            print("location_name "+location_name)
        except Exception as e:
            logger.error(f"Language processing failed, continuing with original: {e}")

        # First try to find in our police station database
        try:
            location_details = get_coordinates_from_location_name(location_name)
            logger.info("Found location in database")
        except Exception as db_error:
            logger.warning(f"Database search failed: {db_error}, trying Google Maps")
            # If database search fails, try Google Maps
            location_details = get_location_from_google_maps(location_name)
            
            # After Google Maps search, try database again with the found location name
            if location_details and location_details.display_name:
                try:
                    logger.info(f"Trying database search again with: {location_details.display_name}")
                    db_location_details = get_coordinates_from_location_name(location_details.display_name)
                    # If found in database, use the database result which has complete info
                    location_details = db_location_details
                    logger.info("Successfully found in database after Google Maps search")
                except Exception as second_db_error:
                    logger.warning(f"Second database search also failed: {second_db_error}, using Google Maps data")
        
        return {
            "data": {
                "location": {
                    "name": location_name,
                    "coordinates": {
                        "lat": location_details.lat,
                        "long": location_details.lon,
                    }
                },
                "nearest_police_station": location_details.nearest_police_station
            }
        }

    except Exception as e:
        logger.error(f"Location processing error: {e}")
        error_message = (
            "The location you entered is outside the jurisdiction of Nashik Gramin Police.\n"
            if language == "english"
            else "आपण दिलेले ठिकाण नाशिक ग्रामीण पोलीसांच्या कार्यक्षेत्राबाहेर आहे.\n"
                 "कृपया आमच्या कार्यक्षेत्रातील वैध ठिकाण प्रविष्ट करा"
        )
        return {
            "message": error_message,
            "next_state": "LOCATION"
        }

def get_coordinates_from_location_name(location_name: str) -> LocationResult:
    """
    Get coordinates and police station info from location name using our database
    """
    try:
        if pi_users is None:
            raise Exception("MongoDB connection not available")


        # Search for police stations with similar names
        police_stations = pi_users.find_one({
                "stationName": {"$regex": location_name, "$options": "i"}
            })


        if not police_stations:
            raise Exception("No police station found with the given name")

        # Pick the first matching station
        matched_station = police_stations

        if not matched_station.get("location") or not matched_station["location"].get("coordinates"):
            raise Exception("Police station coordinates not available")

        coordinates = matched_station["location"]["coordinates"]
        if not coordinates or len(coordinates) < 2:
            raise Exception("Invalid coordinates")

        longitude, latitude = coordinates[0], coordinates[1]

        return LocationResult(
            display_name=matched_station.get("stationName", ""),
            lat=latitude,
            lon=longitude,
            nearest_police_station={
                "_id": str(matched_station.get("_id")),
                "email": matched_station.get("email"),
                "fullName": matched_station.get("fullName"),
                "stationName": matched_station.get("stationName"),
                "address": matched_station.get("address"),
                "officersmobNumber": matched_station.get("mobNumber"),
                "stationMobNumber": matched_station.get("stationMobNumber"),
                "latitude": latitude,
                "longitude": longitude,
                "source": "database"
            }
        )

    except Exception as e:
        logger.error(f"Database search error: {e}")
        raise e

def get_location_from_google_maps(location_name: str) -> LocationResult:
    """
    Fallback to Google Maps API when database search fails
    """
    try:
        if not GOOGLE_MAPS_API_KEY:
            raise Exception("Google Maps API key not available")

        # Use Google Places API to find the location
        places_url = f"https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
        params = {
            'input': location_name + " Nashik",
            'inputtype': 'textquery',
            'fields': 'name,geometry,formatted_address,types',
            'key': GOOGLE_MAPS_API_KEY
        }
        
        response = requests.get(places_url, params=params)
        data = response.json()

        if data['status'] != 'OK' or not data.get('candidates'):
            raise Exception(f"Google Maps API error: {data.get('status')}")

        candidate = data['candidates'][0]
        geometry = candidate.get('geometry', {}).get('location', {})
        
        if not geometry:
            raise Exception("No coordinates found in Google Maps response")

        lat = geometry.get('lat')
        lng = geometry.get('lng')
        
        if not lat or not lng:
            raise Exception("Invalid coordinates from Google Maps")

        # Extract the actual location name from Google Maps
        google_location_name = candidate.get('name', location_name)
        
        # Try to find this location in our database first
        try:
            logger.info(f"Searching database for Google Maps result: {google_location_name}")
            db_result = get_coordinates_from_location_name(google_location_name)
            logger.info(f"Found in database after Google Maps: {db_result.display_name}")
            return db_result
        except Exception as db_error:
            logger.warning(f"Google Maps location not found in database: {db_error}")
            # If not in database, get police station info from Google Maps
            police_station_details = get_nearest_police_station_from_coords(lat, lng)
            
            return LocationResult(
                display_name=google_location_name,
                lat=lat,
                lon=lng,
                nearest_police_station=police_station_details
            )

    except Exception as e:
        logger.error(f"Google Maps search error: {e}")
        raise e

def get_nearest_police_station_from_coords(latitude: float, longitude: float) -> Dict[str, Any]:
    """
    Find nearest police station using Google Places API
    """
    try:
        if not GOOGLE_MAPS_API_KEY:
            return {
                "stationName": "Unknown Police Station",
                "address": "Location found but police station details unavailable",
                "latitude": latitude,
                "longitude": longitude,
                "source": "google_maps_fallback"
            }

        # Search for police stations nearby
        places_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            'location': f'{latitude},{longitude}',
            'radius': 10000,  # 10km radius
            'keyword': 'police station',
            'key': GOOGLE_MAPS_API_KEY
        }
        
        response = requests.get(places_url, params=params)
        data = response.json()

        if data['status'] != 'OK' or not data.get('results'):
            return {
                "stationName": "Nearest Police Station",
                "address": "Police station details not available",
                "latitude": latitude,
                "longitude": longitude,
                "source": "google_maps_no_station"
            }

        # Filter for actual police stations
        valid_police_stations = []
        for place in data['results']:
            name = place.get('name', '').lower()
            types = place.get('types', [])
            
            # Exclude non-police establishments
            excluded_keywords = [
                "academy", "training", "school", "college", "shop", "store",
                "market", "mall", "restaurant", "hotel", "resort", "club",
                "bar", "cafe", "zep", "garud", "outpost", "checkpost"
            ]
            
            is_excluded = any(keyword in name for keyword in excluded_keywords)
            is_police_station = ('police' in name or 'police' in types)
            
            if is_police_station and not is_excluded:
                valid_police_stations.append(place)

        if not valid_police_stations:
            return {
                "stationName": "Police Station",
                "address": "No police station found nearby",
                "latitude": latitude,
                "longitude": longitude,
                "source": "google_maps_no_valid_station"
            }

        # Get the nearest one
        nearest_station = valid_police_stations[0]
        station_location = nearest_station['geometry']['location']
        
        # Get more details
        place_id = nearest_station['place_id']
        details_url = "https://maps.googleapis.com/maps/api/place/details/json"
        details_params = {
            'place_id': place_id,
            'fields': 'name,formatted_address,formatted_phone_number,website',
            'key': GOOGLE_MAPS_API_KEY
        }
        
        details_response = requests.get(details_url, params=details_params)
        details_data = details_response.json()
        
        station_details = details_data.get('result', {}) if details_data.get('status') == 'OK' else {}

        # Try to find this police station in our database
        station_name = station_details.get('name', nearest_station.get('name', 'Police Station'))
        try:
            if pi_users is not None:
                db_station = pi_users.find_one({
                    "$or": [
                        {"stationName": {"$regex": station_name, "$options": "i"}},
                        {"stationName": {"$regex": clean_location_name(station_name), "$options": "i"}}
                    ]
                })
                
                if db_station:
                    logger.info(f"Found police station in database: {db_station.get('stationName')}")
                    coordinates = db_station.get("location", {}).get("coordinates", [])
                    longitude, latitude = coordinates[0], coordinates[1] if coordinates else (station_location['lng'], station_location['lat'])
                    
                    return {
                        "_id": str(db_station.get("_id")),
                        "email": db_station.get("email"),
                        "fullName": db_station.get("fullName"),
                        "stationName": db_station.get("stationName"),
                        "address": db_station.get("address"),
                        "officersmobNumber": db_station.get("mobNumber"),
                        "stationMobNumber": db_station.get("stationMobNumber"),
                        "latitude": latitude,
                        "longitude": longitude,
                    }
        except Exception as db_error:
            logger.warning(f"Could not find police station in database: {db_error}")

        return {
            "stationName": station_name,
            "address": station_details.get('formatted_address', 'Address not available'),
            "stationMobNumber": station_details.get('formatted_phone_number', 'Phone not available'),
            "website": station_details.get('website', ''),
            "latitude": station_location['lat'],
            "longitude": station_location['lng'],
        }

    except Exception as e:
        logger.error(f"Error finding nearest police station: {e}")
        return {
            "stationName": "Police Station",
            "address": "Error retrieving police station details",
            "latitude": latitude,
            "longitude": longitude,
            "source": "error"
        }

def clean_location_name(location_name: str) -> str:
    """
    Clean and normalize location name for database search
    """
    return (
        location_name.strip()
        .lower()
        .replace("  ", " ")
        .replace("police", "")
        .replace("station", "")
        .replace("ps", "")
        .replace("thana", "")
        .replace("chowki", "")
        .strip()
    )

def translate_to_english(text: str) -> str:
    """
    Translate text to English and correct police station names
    """
    try:
        if not openai_client:
            logger.warning("OpenAI client not available, returning original text")
            return text

        # First, correct the police station name format
        corrected_input = correct_police_station_format(text)

        # Check if translation is still needed after correction
        if not needs_translation(corrected_input):
            final_corrected_name = correct_police_station_name_with_gpt(corrected_input)
            return final_corrected_name or corrected_input

        # Use OpenAI for translation
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a translation assistant. Translate the given text into English script only if it is written in Marathi or Hindi, or if it contains spelling mistakes. Return only the corrected translation, without any explanations or extra text."
                },
                {
                    "role": "user",
                    "content": corrected_input
                }
            ]
        )
        
        translation = response.choices[0].message.content.strip()

        # Final correction using GPT with all police station names
        final_corrected_name = correct_police_station_name_with_gpt(translation)
        return final_corrected_name or translation

    except Exception as e:
        logger.error(f"Translation error: {e}")
        return text

def get_all_police_station_names() -> List[str]:
    """
    Get all police station names from both models with Redis caching
    """
    try:
        # Try to get from Redis cache first if available
        if redis_client is not None:
            try:
                cached_data = redis_client.get(POLICE_STATIONS_CACHE_KEY)
                if cached_data:
                    return json.loads(cached_data)
            except redis.RedisError:
                logger.warning("Redis cache unavailable")

        if pi_users is None or sp_users is None:
            raise Exception("Database connections not available")

        # Get station names from both collections
        sp_users_data = list(sp_users.find({}, {"stationName": 1}))
        sp_station_names = [user.get("stationName") for user in sp_users_data if user.get("stationName")]

        pi_users_data = list(pi_users.find({}, {"stationName": 1}))
        pi_station_names = [user.get("stationName") for user in pi_users_data if user.get("stationName")]

        # Combine and deduplicate station names
        all_station_names = list(set(sp_station_names + pi_station_names))

        # Store in Redis cache with TTL if available
        if redis_client is not None:
            try:
                redis_client.setex(POLICE_STATIONS_CACHE_KEY, CACHE_TTL, json.dumps(all_station_names))
            except redis.RedisError:
                logger.warning("Failed to update Redis cache")

        return all_station_names

    except Exception as e:
        logger.error(f"Error fetching police station names: {e}")
        
        # Fallback: try to get from Redis even if there's an error with the database
        if redis_client is not None:
            try:
                cached_data = redis_client.get(POLICE_STATIONS_CACHE_KEY)
                if cached_data:
                    return json.loads(cached_data)
            except Exception as redis_error:
                logger.error(f"Redis fallback also failed: {redis_error}")

        return []

def correct_police_station_name_with_gpt(text: str) -> str:
    """
    Correct police station name using GPT and available station names
    """
    try:
        if not openai_client:
            return text

        all_station_names = get_all_police_station_names()

        if not all_station_names:
            return text

        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": f"""
                    You are a police station name matching assistant.
                    Given a user input and a list of valid police station names, your task is to return the most accurate match.

                    Matching Rules:
                    Return ONLY the corrected police station name if a confident and accurate match exists in the provided list.
                    If no reliable match is found, return the original text.
                    Do not include explanations, comments, or extra text.

                    Consider:
                    Spelling variations
                    Abbreviations (PS, Thana, Chowki, etc.)
                    Common typos
                    Extra words like "city", "town", "near", etc.
                    Prioritize exact or very close matches.
                    reutrn output like ozer police station
                    Available station names: {", ".join(all_station_names[:30])}
                    """
                },
                {
                    "role": "user",
                    "content": f'User input to match: "{text}"'
                }
            ]
        )

        corrected_name = response.choices[0].message.content.strip()

        # Verify the corrected name is actually in our list
        if corrected_name and corrected_name in all_station_names:
            return corrected_name

        return text

    except Exception as e:
        logger.error(f"GPT police station matching error: {e}")
        return text

def correct_police_station_format(text: str) -> str:
    """
    Correct police station format using GPT before matching
    """
    try:
        if not openai_client:
            return text

        all_station_names = get_all_police_station_names()

        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": f"""
                    You are a police station name formatter. Extract and format police station names to match standard formats.

                    Rules:
                    - Remove extra words like "town:", "city:", "ps", "thana", "chowki".
                    - Standardize to "Place Name Police Station".
                    - Correct common spelling mistakes.
                    - If multiple place names are present, keep only the valid police station name.
                    - Only use location names if no station name is provided.
                    - If it doesn't look like a police station name, return the original text.

                    Available station formats: {", ".join(all_station_names[:20]) if all_station_names else "None available"}
                    """
                },
                {
                    "role": "user",
                    "content": text
                }
            ]
        )

        corrected = response.choices[0].message.content.strip()
        return corrected or text

    except Exception as e:
        logger.error(f"Police station format correction error: {e}")
        return text

def needs_translation(text: str) -> bool:
    """
    Check if text needs translation
    """
    if not text:
        return False
        
    # Check for non-English characters (Marathi/Hindi)
    has_non_english = bool(re.search(r'[\u0900-\u097F]', text))

    # Check for obvious spelling mistakes or abbreviations
    has_common_mistakes = bool(re.search(r'(ps|thana|chowki|नाका|थाना)', text, re.IGNORECASE))

    # Check if it's all uppercase (might need normalization)
    is_all_uppercase = text == text.upper() and text != text.lower()

    return has_non_english or has_common_mistakes or is_all_uppercase

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two coordinates using Haversine formula
    """
    R = 6371  # Earth's radius in kilometers
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    
    a = (math.sin(d_lat / 2) * math.sin(d_lat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(d_lon / 2) * math.sin(d_lon / 2))
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c * 1000  # Convert to meters
    
    return round(distance)

# Example usage and test function
def main():
    # Test with various inputs
    test_inputs = [
        "ozar Police Station",
        # "वाणी पोलीस स्टेशन",  # Marathi
        # "vani ps",
        # "Vani Thana",
        # "Nashik",  # City name
        # "Mumbai"   # Outside Nashik (should fail)
    ]
    
    for test_input in test_inputs:
        print(f"\nTesting: '{test_input}'")
        try:
            result = location_selector(test_input, "english")
            print(result)
            # if "nearest_police_station" in result.get("data", {}):
            #     station = result["data"]["nearest_police_station"]
            #     print(f"✓ Found: {station.get('stationName')}")
            #     print(f"  Location: {station.get('latitude')}, {station.get('longitude')}")
            #     print(f"  Address: {station.get('address')}")
            #     print(f"  Source: {station.get('source', 'unknown')}")
            #     if station.get('mobNumber'):
            #         print(f"  Mobile: {station.get('mobNumber')}")
            #     if station.get('stationMobNumber'):
            #         print(f"  Station Mobile: {station.get('stationMobNumber')}")
            # else:
            #     print(f"✗ Error: {result.get('message')}")
        except Exception as e:
            print(f"✗ Exception: {e}")

if __name__ == "__main__":
    main()