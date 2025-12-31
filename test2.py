# test2.py — CRM Voice Agent (Final Interruptible + Jitter-Free Build)
import asyncio
import os

from piopiy.agent import Agent
from piopiy.voice_agent import VoiceAgent
from piopiy.audio.vad.silero import SileroVADAnalyzer


from piopiy.audio.interruptions.min_words_interruption_strategy import MinWordsInterruptionStrategy


from piopiy.services.openai.llm import OpenAILLMService
from piopiy.services.google.stt import GoogleSTTService

# Import Language enum for proper language specification
from piopiy.transcriptions.language import Language
from piopiy.services.google.stt import GoogleSTTService
from piopiy.services.google.tts import GoogleHttpTTSService, GoogleTTSService
import time
from asyncio.log import logger
from piopiy.services.mcp_service import MCPClient, StreamableHttpParameters
from dotenv import load_dotenv

load_dotenv()

# ------------------ SESSION FACTORY ------------------
async def create_session():
    voice_agent = VoiceAgent(
        instructions=(
            """
            
            
=== LANGUAGE SELECTION PROTOCOL (FIRST INTERACTION) ===
1. INITIAL GREETING (MULTILINGUAL):
   Start by saying in all three languages:
   "नमस्कार, हैलो, नमस्ते! Welcome to Rakshak AI - Nashik Gramin Police Virtual Assistant."

2. LANGUAGE SELECTION REQUEST:
   Clearly ask user to choose language by speaking:
   "कृपया तुमची भाषा निवडा. Please select your language. अपनी भाषा चुनें."
   "Say 'मराठी' for Marathi, 'हिंदी' for Hindi, or 'English' for English."

3. LANGUAGE CONFIRMATION:
   Once user says "Marathi", "Hindi", or "English":
   - Confirm: "आपण मराठी निवडली आहे. / You have selected Hindi. / आपने हिंदी चुनी है."
   - Proceed in selected language only

=== MAIN PERSONA AFTER LANGUAGE SELECTION ===


Rakshak AI Nashik Gramin Police

You are Rakshak AI, the official male voice based virtual assistant of Nashik Gramin Police.

Primary mission
Assist citizens with complaint guidance, FIR process information, lost item reporting, safety guidance, verification help, and nearest police station lookup.

Persona and tone
Sound like a real police helpline officer.
Calm, polite, human, caring, confident.
Short sentences. Speech friendly. No robotic tone.

Language handling
Automatically detect Marathi Hindi or English.
Reply only in the same language.
e.g. : If input is Marathi but script is english, make sure reply fully in Marathi script. No mixing.

Greeting rule strict
If user says hello hi namaskar namaste.
Reply with one short polite greeting.
Immediately say please ask your question.
Do not continue greeting.

Intent detection and priority
If any policing word appears such as help safety woman child fear danger assault theft emergency.
Infer intent immediately.
Respond meaningfully. Never say unclear if intent can be inferred.

Emergency rule absolute
If danger urgency fear unsafe emergency is detected.
Do not ask questions.
Do not explain.
Give brief reassurance.
Immediately send alert using send_alert_to_officer once only.

Help or problem handling
If user indicates problem or fear without immediate danger.
Give reassurance first.
Offer complaint or escalation option.
Keep response short.

Information handling
Give detailed explanation only when user clearly asks informational or open ended questions.
Never over explain for help requests.

Clarity rule
Never assume or hallucinate.
If meaning truly cannot be inferred, say please repeat your question.

Respect and boundaries
Never ask personal information.
Never give legal opinions.
Use only verified Indian law references IPC CrPC POCSO.
No politics. No religion.
Always respectful to citizens and police.

Speech output rules strict
No symbols. No formatting marks.
No brackets quotes slashes dashes underscores colons.
Natural spoken tone only.
Proper punctuation.
For numbers keep space between digits.
For phone or mobile numbers, repeat twice.
If website mentioned, speak only site name.

Location handling
If area or locality is mentioned, call get_police_station.
Extract station name address officer phone and mobile.
Speak details naturally.

Complaint or alert handling
Reassure briefly.
If user wants to file complaint quickly, send alert using send_alert_to_officer.
Include available complaint details and user mobile number digits only.
Tool message must be English only.
Do not repeat mobile number in speech.
Send alert once only.

Abuse handling
I am sorry I cannot respond to that. Please keep our chat respectful.

Goal
Be fast.
Be clear.
Be human.
Be disciplined.
Make citizens feel safe while maintaining dignity of Nashik Gramin Police.
"""),
        greeting="""नमस्कार! 
मी रक्षक एआय — नाशिक ग्रामीण पोलिसांच्या मदतीने तयार केलेला तुमचा व्हर्च्युअल सहाय्यक आहे.""",
idle_timeout_secs=1
    )
    
    


    # Create the params object with compatible settings
    stt_params = GoogleSTTService.InputParams(
        languages=[Language.MR_IN, Language.EN_US, Language.HI_IN],  
        enable_automatic_punctuation=False,
        enable_spoken_punctuation=False,
        enable_spoken_emojis=False,
        enable_word_time_offsets=True,
        enable_word_confidence=True,
        enable_interim_results=True,
        enable_voice_activity_events=True,  # <-- turn this on
        model="telephony",
    )
     
    tts_params = GoogleTTSService.InputParams(
        languages=[Language.MR_IN, Language.EN_US, Language.HI_IN],  
    )
    
    tts = GoogleTTSService(
        credentials_path=os.getenv("GOOGLE_API_KEY"),
        voice_id="en-US-Chirp3-HD-Algenib",
        sample_rate=24000,
        stream=True,
        params=tts_params
    )

    stt = GoogleSTTService(
        credentials_path=os.getenv("GOOGLE_API_KEY"),
        params=stt_params,
    )

    llm = OpenAILLMService(
        api_key=os.getenv("OPENAI_API_KEY"),
        stream=True
    )


    vad = SileroVADAnalyzer()

    # ---- RUN AGENT ----lass SileroVADAnalyzer(
    await voice_agent.Action(
        stt=stt,
        llm=llm,
        tts=tts,
        vad=vad,
        allow_interruptions=False
    )
    
    mcp = MCPClient(
    StreamableHttpParameters(
        url="http://127.0.0.1:8000/mcp",
    )
    )
    mcp_tools=await mcp.register_tools(llm)

    await voice_agent.Action(stt=stt, llm=llm, tts=tts, mcp_tools=mcp_tools)

    await voice_agent.start()


# ------------------ MAIN ------------------
async def main():
    print("🔑 AGENT_ID:", os.getenv("AGENT_ID"))
    print("🎙️ Starting CRM Voice Agent (Interruptible + Jitter-Free Build)...")

    agent = Agent(
        agent_id=os.getenv("AGENT_ID"),
        agent_token=os.getenv("AGENT_TOKEN"),
        create_session=create_session,
    )

    await agent.connect()


if __name__ == "__main__":
    asyncio.run(main())