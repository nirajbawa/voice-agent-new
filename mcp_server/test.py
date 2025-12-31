import asyncio
from utils.location import search_village_fuzzy

async def test_spelling_mistakes():
    # Test cases with common spelling mistakes
    test_cases = [
        "Kurangaonwadi",      # Correct
        "kurangaonwadi",      # lowercase
        "Kurangaon Wadi",     # Extra space
        "Kurangaonvadi",      # Missing 'w'
        "Kurangaonwadi ",     # Trailing space
        "Kurangoonwadi",      # Double 'o'
        "Kurangaon",          # Partial
        "Devagaon",           # Correct
        "Devagaoon",          # Double 'o'
        "Deogaon",            # Missing 'va'
        "Devgaon",            # Missing 'a'
        "WrongVillage",       # Doesn't exist
    ]
    
    print("Testing with spelling mistakes:\n")
    
    for village_name in test_cases:
        print(f"\nSearching: '{village_name}'")
        village, station, score = await search_village_fuzzy(village_name)
        
        if village and station:
            print(f"✓ Match: {village['villagename']} (Score: {score:.2f})")
            print(f"  → Police Station: {station['stationName']}")
        elif village:
            print(f"✓ Village found: {village['villagename']} (Score: {score:.2f})")
            print(f"  → No station data")
        elif score > 0.3:  # Show suggestions for close matches
            print(f"✗ Not found, but similar villages might exist")
        else:
            print(f"✗ No match found")

asyncio.run(test_spelling_mistakes())