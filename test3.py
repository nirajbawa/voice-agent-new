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
            # Try different switching methods
            try:
                await stt_services.switch_service(marathi_stt)
                await tts_services.switch_service(marathi_tts)
            except:
                # Fallback: Restart with Marathi services
                pass
            return "Switched to Marathi"
            
        elif language in ["hindi", "hi", "हिंदी"]:
            await stt_services.switch_service(hindi_stt)
            await tts_services.switch_service(hindi_tts)
            return "Switched to Hindi"
            
        elif language in ["english", "en", "eng", "अंग्रेजी"]:
            await stt_services.switch_service(english_stt)
            await tts_services.switch_service(english_tts)
            return "Switched to English"
        
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
    
    voice_agent.add_tool(language_tool_schema, change_assistant_language_handler)
    
    # 2. GET MCP TOOLS
    mcp_tools = []
    try:
        mcp = MCPClient(StreamableHttpParameters(url="http://127.0.0.1:8000/mcp"))
        mcp_tools = await mcp.register_tools(llm)
        print(f"✅ Loaded MCP tools: {[t.name for t in mcp_tools]}")
    except Exception as e:
        print(f"⚠️ MCP failed: {e}")
    
    # 3. START ACTION WITH BOTH
    await voice_agent.Action(
        stt=stt_services,
        llm=llm, 
        tts=tts_services,
        mcp_tools=mcp_tools,
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