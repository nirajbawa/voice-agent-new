# test2.py — CRM Voice Agent with Conflict Resolution
import asyncio
import os
from dotenv import load_dotenv

from piopiy.agent import Agent
from piopiy.voice_agent import VoiceAgent
from piopiy.audio.vad.silero import SileroVADAnalyzer
from piopiy.services.openai.llm import OpenAILLMService
from piopiy.services.google.stt import GoogleSTTService
from piopiy.services.google.tts import GoogleTTSService
from piopiy.transcriptions.language import Language
from piopiy.services.mcp_service import MCPClient, StreamableHttpParameters
from piopiy.pipeline.service_switcher import ServiceSwitcher, ServiceSwitcherStrategyManual
from piopiy.adapters.schemas.function_schema import FunctionSchema
from mcp_server.utils.sendWhatsappMessage import send_whatsapp_message
load_dotenv()

async def create_session(call_id: str, agent_id: str, from_number: str, to_number: str):
    
    print(f"📞 Call from: {from_number} to: {to_number}")
    
    voice_agent = VoiceAgent(
        instructions=(
            """
CRITICAL: TWO SEPARATE TOOL CATEGORIES

1. LANGUAGE TOOL (use this FIRST for language requests):
   Tool name: "change_assistant_language"
   Use for: "भाषा बदला", "मराठी", "हिंदी", "English", "speak in", language change
   Examples:
   - "भाषा बदला" → change_assistant_language({"language": "marathi"})
   - "मराठी" → change_assistant_language({"language": "marathi"})
   - "speak in Hindi" → change_assistant_language({"language": "hindi"})

2. POLICE TOOLS (use these for police work):
   - get_police_station: For locations ONLY like "नाशिक", "मुंबई"
   - send_alert_to_officer: For emergencies

IMPORTANT: Language names (मराठी, हिंदी, English) are NOT locations.
Never use get_police_station for language requests.

call this function for emergenyc to send alert to police officer : send_alert_to_officer(message) make sure this message in english

You are Rakshak AI, the official male voice based virtual assistant of Nashik Gramin Police.
Your primary mission is to assist citizens with police-related inquiries.
"""),
        greeting="""Welcome to Nashik Gramin Police. Please select language: Say Marathi, Hindi, or English.""",
        idle_timeout_secs=120
    )

    # Create STT and TTS services (same as before)
    marathi_stt = GoogleSTTService(
        credentials_path=os.getenv("GOOGLE_API_KEY"),
        params=GoogleSTTService.InputParams(languages=[Language.MR_IN],
                                                    enable_automatic_punctuation=False,
        enable_spoken_punctuation=False,
        enable_spoken_emojis=False,
        enable_word_time_offsets=True,
        enable_word_confidence=True,
        enable_interim_results=True,
        enable_voice_activity_events=True,
        model="latest_long"),
    )
    
    hindi_stt = GoogleSTTService(
        credentials_path=os.getenv("GOOGLE_API_KEY"),
        params=GoogleSTTService.InputParams(languages=[Language.HI_IN],
                                                    enable_automatic_punctuation=False,
        enable_spoken_punctuation=False,
        enable_spoken_emojis=False,
        enable_word_time_offsets=True,
        enable_word_confidence=True,
        enable_interim_results=True,
        enable_voice_activity_events=True,
        model="latest_long"),
    )
    
    english_stt = GoogleSTTService(
        credentials_path=os.getenv("GOOGLE_API_KEY"),
        params=GoogleSTTService.InputParams(languages=[Language.EN_US], 
                                                    enable_automatic_punctuation=False,
        enable_spoken_punctuation=False,
        enable_spoken_emojis=False,
        enable_word_time_offsets=True,
        enable_word_confidence=True,
        enable_interim_results=True,
        enable_voice_activity_events=True,
        model="latest_long"),
    )

    marathi_tts = GoogleTTSService(
        credentials_path=os.getenv("GOOGLE_API_KEY"),
        voice_id="en-US-Chirp3-HD-Algenib",
        params=GoogleTTSService.InputParams(languages=[Language.MR_IN])
    )
    
    hindi_tts = GoogleTTSService(
        credentials_path=os.getenv("GOOGLE_API_KEY"),
        voice_id="en-US-Chirp3-HD-Algenib",
        params=GoogleTTSService.InputParams(languages=[Language.HI_IN])
    )
    
    english_tts = GoogleTTSService(
        credentials_path=os.getenv("GOOGLE_API_KEY"),
        voice_id="en-US-Chirp3-HD-Algenib",
        params=GoogleTTSService.InputParams(languages=[Language.EN_US])
    )

    stt_services = ServiceSwitcher(
        services=[marathi_stt, hindi_stt, english_stt],
        strategy_type=ServiceSwitcherStrategyManual
    )
    
    tts_services = ServiceSwitcher(
        services=[marathi_tts, hindi_tts, english_tts],
        strategy_type=ServiceSwitcherStrategyManual
    )

    llm = OpenAILLMService(
        api_key=os.getenv("OPENAI_API_KEY"),
        stream=True,
        system_language_awareness=True 
    )

    vad = SileroVADAnalyzer()
    
    # 1. ADD LANGUAGE TOOL FIRST (with unique name)
    async def change_assistant_language_handler(params):
        language = params.arguments.get("language", "").lower()
        print(f"🔄 Switching to: {language}")
        
        if language in ["marathi", "mr", "मराठी"]:
            await voice_agent.switch_service(marathi_stt)
            await voice_agent.switch_service(marathi_tts)
            await params.result_callback(f"Switched to Hindi")
            return "Switched to Marathi"
            
        elif language in ["hindi", "hi", "हिंदी"]:
            await voice_agent.switch_service(hindi_stt)
            await voice_agent.switch_service(hindi_tts)
            await params.result_callback(f"Switched to Hindi")
            return "Switched to Hindi"
            
        elif language in ["english", "en", "eng", "अंग्रेजी"]:
            await voice_agent.switch_service(english_stt)
            await voice_agent.switch_service(english_tts)
            await params.result_callback(f"Switched to English")
            return "Switched to English"
        await params.result_callback(f"Unknown language: {language}")
        return f"Unknown language: {language}"
    
    language_tool_schema = FunctionSchema(
        name="change_assistant_language",  # Unique name
        description="Change the assistant's operating language. Use for language-related requests only.",
        properties={
            "language": {
                "type": "string",
                "enum": ["marathi", "hindi", "english"],
                "description": "Language to switch to"
            }
        },
        required=["language"]
    )
    
    async def send_alert_to_officer(params):
        print("called alert")
        alert_message = params.arguments.get("message", "").lower()
        print(alert_message)
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
                            "text": alert_message
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
        await params.result_callback("alert sended to the officer they will contact you shortly.")
        return f"alert sended to the officer they will contact you shortly."


    
    alert_officer_schema = FunctionSchema(
        name="send_alert_to_officer",  # Unique name
        description="send the alert to police officer for help to control room",
        properties={
            "message": {
                "type": "string",
                "description": "details of incident in short"
            }
        },
        required=["message"]
    )
    
    async def search_police_station(param):
        print("location called")
    
    
    search_police_station_schema = FunctionSchema(
        name="send_alert_to_officer",  # Unique name
        description="send the alert to police officer for help to control room",
        properties={
            "message": {
                "type": "string",
                "description": "details of incident in short"
            }
        },
        required=["message"]
    )
    
    
    voice_agent.add_tool(language_tool_schema, change_assistant_language_handler)
    voice_agent.add_tool(alert_officer_schema, send_alert_to_officer)
    voice_agent.add_tool(search_police_station_schema, send_alert_to_officer)
    

    
    # # 3. START ACTION WITH BOTH
    await voice_agent.Action(
        stt=stt_services,
        llm=llm, 
        tts=tts_services,
        allow_interruptions=False, 
        vad=vad
    )

    await voice_agent.start()

async def main():
    print("🚀 Starting agent with conflict-free language switching...")
    agent = Agent(
        agent_id=os.getenv("AGENT_ID"),
        agent_token=os.getenv("AGENT_TOKEN"),
        create_session=create_session,
    )
    await agent.connect()

if __name__ == "__main__":
    asyncio.run(main())