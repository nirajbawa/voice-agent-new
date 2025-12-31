from dotenv import load_dotenv
load_dotenv()
from mcp.server.fastmcp import FastMCP
from utils.location import search_village_fuzzy
from utils.sendWhatsappMessage import send_whatsapp_message
import os
# Stateful server (maintains session state)
mcp = FastMCP("StatefulServer")

# Add a simple tool to demonstrate the server
@mcp.tool()
async def get_police_station(area_name) -> str:
    print(area_name)
    village, station, score = await search_village_fuzzy(area_name)
    print(f"✓ Match: {village['villagename']} (Score: {score:.2f})")
    print(f"  → Police Station: {station['stationName']}")
    return f"police {station}"

@mcp.tool()
async def send_alert_to_officer(message) -> str:
    print(message)
    template_message = {
        "name": "alert_message_to_officer",
        "language": {
            "code": "en",
        },
        "components": [
            {
                "type": "body",
                "parameters": [
                    {
                        "type": "text",
                        "text": message
                    } 
                ]
            }
        ]
    }
    out = await send_whatsapp_message(
        phone_number=os.getenv("OFFICER_NUMBER"),
        message=template_message,
        is_template="template_with_components"
    )
    
    print(out)
    
    return f"alert sended to the officer they will contact you shortly."



# if __name__ == "__main__":
#     asyncio.run(get_police_station())


# Run server with streamable_http transport
if __name__ == "__main__":
    mcp.run(transport="streamable-http")