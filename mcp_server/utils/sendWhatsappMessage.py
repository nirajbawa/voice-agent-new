import asyncio
import aiohttp
import os
from typing import Union, Dict, Any
from dotenv import load_dotenv

load_dotenv(dotenv_path="/home/ubuntu/testing/mcp_server/.env")

FACEBOOK_BASE_URL = os.getenv("FACEBOOK_BASE_URL")

def format_whatsapp_message(
    message: Union[str, Dict[str, str]], 
    language: str = "english"
) -> str:
    """
    Format WhatsApp message content while preserving newlines
    """
    if isinstance(message, str):
        content = message
    else:
        content = message.get(language) or message.get("english") or ""
    
    if not content:
        return ""
    
    content = (
        content
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    
    lines = content.split("\n")
    cleaned_lines = [line.strip(" \t") for line in lines]
    content = "\n".join(cleaned_lines)
    content = "\n\n".join([part for part in content.split("\n\n\n") if part])
    
    return content

async def send_whatsapp_message(
    phone_number: str,
    message: Any,
    is_template: str = "custom"
) -> bool:
    """
    Send WhatsApp message using Facebook Graph API with aiohttp
    """
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
    }
    
    if is_template == "template":
        payload["type"] = "template"
        payload["template"] = message
    elif is_template == "template_with_components":
        payload["type"] = "template"
        payload["template"] = message
    elif is_template == "interactive":
        payload["type"] = "interactive"
        payload.update(message)
    else:
        formatted_message = format_whatsapp_message(message)
        payload["type"] = "text"
        payload["text"] = {"body": formatted_message}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{FACEBOOK_BASE_URL}/{os.getenv('WHATSAPP_PHONE_ID')}/messages",
                json=payload,
                headers={
                    "Authorization": f"Bearer {os.getenv('WHATSAPP_ACCESS_TOKEN')}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                print(response)
                return response.status == 200
                
    except aiohttp.ClientError as e:
        print(f"WhatsApp API error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

async def main():
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
                        "text": "User lost a laptop worth seventy five thousand rupees. The laptop has a slight screen problem. Kindly assist in recovery. User's contact: 7020547519"
                    } 
                ]
            }
        ]
    }
    
    out = await send_whatsapp_message(
        phone_number="9359839551",
        message=template_message,
        is_template="template_with_components"
    )
    
    print(out)

if __name__ == "__main__":
    asyncio.run(main())