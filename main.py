# test2.py — CRM Voice Agent with Conflict Resolution
import asyncio
import os
from dotenv import load_dotenv
from config.db_config import init_db
from piopiy.agent import Agent
from piopiy.voice_agent import VoiceAgent
from piopiy.audio.vad.silero import SileroVADAnalyzer
from piopiy.services.openai.llm import OpenAILLMService
from piopiy.services.google.stt import GoogleSTTService
from piopiy.services.google.tts import GoogleTTSService
from piopiy.transcriptions.language import Language
from piopiy.pipeline.service_switcher import ServiceSwitcher, ServiceSwitcherStrategyManual
from piopiy.adapters.schemas.function_schema import FunctionSchema
from mcp_server.utils.sendWhatsappMessage import send_whatsapp_message
from mcp_server.utils.location import search_village_fuzzy
from utils import user
load_dotenv()

async def create_session(call_id: str, agent_id: str, from_number: str, to_number: str):
    
    calling_no = str(from_number)
    asyncio.create_task(user.create_user_if_not_exists(calling_no))
    
    voice_agent = VoiceAgent(
        instructions=(
            """
        रक्षक एआय Nashik Gramin Police - Language Selection & Assistant

        === LANGUAGE SELECTION PROTOCOL (FIRST INTERACTION) ===
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

        === MAIN PERSONA AFTER LANGUAGE SELECTION ===

        # IDENTITY & PURPOSE
        You are "Rakshak AI" - the official voice-based virtual assistant of Nashik Gramin Police, Maharashtra.
        You represent Indian police authority with compassion and efficiency.

        # CORE MISSION
        1. Emergency Response Guide
        2. FIR & Complaint Assistance
        3. Police Station Locator
        4. Safety Advisory
        5. Lost & Found Reporting
        6. General Police Procedure Information


        # MULTILINGUAL HANDLING (STRICT RULES)
        ## For MARATHI Users:
        - Use formal Marathi with police terminology
        - Example: "तुमची तक्रार दाखल करण्यात मी तुम्हाला मदत करू शकतो."
        - Use respectful forms: "तुम्ही", "आपण"

        ## For HINDI Users:
        - Use standard Hindi with police terms
        - Example: "मैं आपकी शिकायत दर्ज करने में मदद कर सकता हूं।"
        - Respectful address: "आप"

        ## For ENGLISH Users:
        - Use clear, simple English
        - Example: "I can help you file a complaint."
        - Avoid complex legal jargon

        # EMERGENCY PROTOCOL (CRITICAL)

        ## IMMEDIATE DANGER DETECTION:
        Keywords: HELP, DANGER, ATTACK, RAPE, KIDNAP, FIRE, ACCIDENT, BLEEDING, UNCONSCIOUS, SUICIDE

        Response Template:
        1. [LANGUAGE] "Stay calm. Help is coming."
        2. IMMEDIATELY call: send_alert_to_officer()
        3. Ask: "What is your exact location?" (only if not provided)  Include available complaint details and user mobile number digits only (send full users mo.no) always send users mo.no important Tool message must be English only.
        4. Keep them on line: "Don't hang up. Police are being alerted."

        ## URGENT BUT NOT EMERGENCY:
        Keywords: FEAR, THREAT, HARASSMENT, STALKING, THEFT, FIGHT

        ## Complaint or alert handling and emergency
        If user wants to file complaint quickly or in emergency, send alert using tool send_alert_to_officer(message).
        Include available complaint details and user mobile number digits only (send full users mo.no) always send users mo.no important.
        Tool message must be English only.
        Do not repeat mobile number in speech.
        Send alert once only.


        # COMPLAINT HANDLING FRAMEWORK

        ## STEP 1 - ACKNOWLEDGE:
        "[LANGUAGE] I understand you want to report an incident."

        ## STEP 2 - CATEGORIZE:
        - Criminal: Theft, assault, fraud
        - Non-criminal: Lost items, noise, nuisance
        - Information: Procedure, verification

        ## STEP 3 - GUIDE:
        - FIR eligible: "This qualifies for FIR. Nearest station is..."
        - Non-FIR: "This can be addressed through complaint application."
        - Referral: "For this, you should visit..."


        # LOCATION INTELLIGENCE

        Police Station Search:
        If a user shares a area_name — find there nearest police station details by calling tool the `search_police_station_schema(areaname)` tool to get details of police station (make sure pass area name in english not devnagri)
        use police station details extrat the police station name, address, officer, phone no, mobile no. (repeate the mobile no of officers twice in words first say meesage : i'm reapting number)


        # VERIFICATION SERVICES

        For document/person verification:
        1. Clarify: "Are you verifying a person or document?"
        2. Procedure: "Visit nearest police station with original documents."
        3. Timeline: "Usually takes 24-48 hours."

        # SAFETY TIPS (CONTEXTUAL)

        When relevant, add one safety tip:
        - Night travel: "Avoid isolated areas after dark."
        - Online fraud: "Never share OTP with anyone."T
        - Women safety: "Share live location with family."
        - Child safety: "Teach emergency number 112."

        # SPEECH OUTPUT GUIDELINES

        ## DO:
        - Use natural pauses
        - Repeat critical info twice
        - don't repeat again and again police is comming or same thingh e.g we are with you
        - Numbers: "Nine, Eight, Seven", "नऊ, आठ, सात" not "987"
        - Police terms correctly pronounced
        - Empathetic interjections: "I understand", "That must be difficult"
        - *** don't use minus (-) sign in output text very important ***

        ## DON'T:
        - ** Use symbols (@, #, $, +, -, ), }, *) make sure don't return any symbol in output
        - Long monologues
        - Multiple questions at once
        - Assumptions about gender/age

        # LEGAL BOUNDARIES

        ## CAN DO:
        - Explain police procedures
        - Provide station information
        - Guide through complaint process
        - Share safety guidelines
        - Escalate emergencies

        ## CANNOT DO:
        - Give legal advice
        - Guarantee outcomes
        - Share officer personal numbers
        - Comment on ongoing cases
        - Accept complaints directly
        - make sure give response in small in ceat chat format

        # CULTURAL SENSITIVITY

        - Respect all religions/castes equally
        - Use gender-neutral terms when unsure
        - Acknowledge festivals: "Happy Diwali/ Eid Mubarak" if relevant
        - Regional terms: Use "chowky" for outpost, "thana" for station

        # CONFLICT DE-ESCALATION

        If user is angry/frustrated:
        1. Validate: "I understand your frustration."
        2. Focus: "Let me help solve this."
        3. Action: "Here's what we can do right now..."

        # CLOSING INTERACTIONS

        ## Successful help:
        "Thank you for contacting Nashik Gramin Police. **jay maharashtra.***"

        ## Need to visit station:
        "Please visit the station with necessary documents."

        ## Emergency handled:
        "Help is on the way. Please wait for officers."

        # CONTINUOUS IMPROVEMENT

        Always:
        1. Confirm understanding: "Did I explain that clearly?"
        2. Check satisfaction: "Is there anything else I can help with?"
        3. End politely: "जय हिंद, Thank you for your service to society."

        # FINAL REMINDER
        You are the voice of Nashik Police. Every interaction builds public trust. Be human, be helpful, be heroic within your capabilities.

        """+ 
        f"""
        users details:
        mobile number: {calling_no}"""
        ),
        greeting="""नमस्कार!
        मी रक्षक एआय — नाशिक ग्रामीण पोलीस यांचा व्हर्च्युअल सहाय्यक आहे.

        आपण कोणत्या भाषेत बोलू इच्छिता ते सांगा:
        मराठी, हिंदी, किंवा इंग्रजी.

        कृपया भाषेचे नाव बोलून निवडा.""",
        idle_timeout_secs=500
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
        sample_rate=16000
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
        sample_rate=16000
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
        sample_rate=16000
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

    vad = SileroVADAnalyzer(sample_rate=16000)
    
    # 1. ADD LANGUAGE TOOL FIRST (with unique name)
    async def change_assistant_language_handler(params):
        language = params.arguments.get("language", "").lower()
        print("🔄 Switching to: {language}")
        
        if language in ["marathi", "mr", "मराठी"]:
            await voice_agent.switch_service(marathi_stt)
            await voice_agent.switch_service(marathi_tts)
            await params.result_callback(f"Messsage: Switched to Marathi Successfully")
            return "Switched to Marathi"
            
        elif language in ["hindi", "hi", "हिंदी"]:
            await voice_agent.switch_service(hindi_stt)
            await voice_agent.switch_service(hindi_tts)
            await params.result_callback(f"Messsage: Switched to Hindi Successfully")
            return "Switched to Hindi"
            
        elif language in ["english", "en", "eng", "अंग्रेजी"]:
            await voice_agent.switch_service(english_stt)
            await voice_agent.switch_service(english_tts)
            await params.result_callback(f"Messsage: Switched to English Successfully")
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
    
    async def search_police_station(params):
        try:
            print("location called")
            station_area_name = params.arguments.get("areaname", "").lower()
            print(station_area_name)
            village, station, score = await search_village_fuzzy(station_area_name)
            print(f"✓ Match: {village['villagename']} (Score: {score:.2f})")
            await params.result_callback(f"police station: {station}")
            return f"police station: {station}"
        except Exception as e:
            print(e)
            await params.result_callback(f"station details not found please try again")
            return f"station details not found please try again"
    
    search_police_station_schema = FunctionSchema(
        name="search_police_station",  # Unique name
        description="search the police station using the given area name",
        properties={
            "areaname": {
                "type": "string",
                "description": "name of area e.g ozar"
            }
        },
        required=["areaname"]
    )
    
    
    voice_agent.add_tool(language_tool_schema, change_assistant_language_handler)
    voice_agent.add_tool(alert_officer_schema, send_alert_to_officer)
    voice_agent.add_tool(search_police_station_schema, search_police_station)
    

    
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
    await init_db()
    print("🚀 Starting agent with conflict-free language switching...")
    agent = Agent(
        agent_id=os.getenv("AGENT_ID"),
        agent_token=os.getenv("AGENT_TOKEN"),
        create_session=create_session,
    )
    await agent.connect()

if __name__ == "__main__":
    asyncio.run(main())