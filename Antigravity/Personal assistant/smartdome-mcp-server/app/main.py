import os
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from zep_cloud.client import Zep
from zep_cloud.types import Message

# --- CONFIG ---
GOOGLE_API_KEY = "AIzaSyDdVm6dbiYsJbTs3rFm7rQ-HZtiRCuZ2DM"
ZEP_API_KEY = "z_1dWlkIjoiYjRlMjk5ODAtMDI4Ny00YWE0LTk5NGEtOTI4NTkwODYwMDZhIn0.NRyujHSnh4o6f2gVK6zZPxydg1jfuhSXBgGaYL6CRlJFBeLveCiVYaqZ8y2bKZBEu-Mk9gDoAGzBn8wSHvmMcQ"

client = genai.Client(api_key=GOOGLE_API_KEY)
zep = Zep(api_key=ZEP_API_KEY)

# SAFETY OFF
SAFETY_CONFIG = types.GenerateContentConfig(
    safety_settings=[
        types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
        types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
        types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
        types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
    ]
)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- 🔥 НОВАТА СТРУКТУРА (HAPM ROLES) 🔥 ---
AGENT_PERSONAS = {
    # 1. ВАЛЕНТИН (СТРАТЕГИЯ)
    "ceo": """
    IDENTITY: Virtual CEO. Partner to Valentin Stoyanov.
    FOCUS: Strategy, Investment, High-level Vision.
    PROTOCOL: Be brief, strategic, and decisive. Report on Risks and Capital.
    LANGUAGE: Bulgarian.
    """,

    # 2. КАМЕН (СОФТУЕР & ДАННИ) - НОВАТА ТИ РОЛЯ
    "cio": """
    IDENTITY: Virtual CIO (Chief Information Officer). Partner to Kamen Bouakkaz.
    FOCUS: The Digital Brain. SmartDome OS, Software Stack (FastAPI/React), AI Orchestration, Notion Integration, Data Security.
    PROTOCOL: Technical depth, System Architecture, Debugging logs.
    LANGUAGE: Bulgarian.
    """,

    # 3. БИСЕР (ХАРДУЕР & СТРОЕЖ) - НОВАТА РОЛЯ НА БИСЕР
    "cto": """
    IDENTITY: Virtual CTO (Chief Technology Officer). Partner to Biser Petrov.
    FOCUS: The Physical Hardware. Construction Technology, Materials, 3D Printing, Structural Engineering, Physics, On-site operations.
    PROTOCOL: Engineering precision, Material science, Physics calculations.
    LANGUAGE: Bulgarian.
    """
}

@app.post("/chat")
async def chat_endpoint(
    text: str = Form(None),
    file: UploadFile = File(None),
    agent_role: str = Form("ceo"), # Frontend sends 'ceo', 'cio', 'cto'
    thread_id: str = Form("default_thread"),
    user_id: str = Form("kamen_architect")
):
    # Избираме правилната персона
    base_prompt = AGENT_PERSONAS.get(agent_role, AGENT_PERSONAS["ceo"])
    
    # MEMORY
    try:
        memory = zep.thread.get_history(thread_id=thread_id, limit=10)
        if memory.messages:
            hist = "\n".join([f"{m.role}: {m.content}" for m in memory.messages])
            base_prompt += f"\n\n=== MEMORY ===\n{hist}\n==============\n"
    except: pass

    # FILE HANDLING
    file_content = None
    file_mime = None
    transcribed_text = None
    
    if file:
        content = await file.read()
        if "audio" in file.content_type or file.filename.endswith('.webm'):
            file_content = content
            file_mime = "audio/webm"
            
            # STEP 1: Transcribe the audio first
            try:
                transcribe_resp = client.models.generate_content(
                    model="gemini-2.0-flash-exp",
                    contents=[types.Content(role="user", parts=[
                        types.Part.from_text(text="Transcribe this audio to text. Return ONLY the transcribed text, nothing else."),
                        types.Part.from_bytes(data=file_content, mime_type=file_mime)
                    ])],
                    config=SAFETY_CONFIG
                )
                transcribed_text = transcribe_resp.text.strip()
            except Exception as e:
                return {"response": f"Transcription Error: {str(e)}"}
        else:
            try:
                txt = content.decode("utf-8")
                base_prompt += f"\n\n=== UPLOADED FILE ===\n{txt}\n=====================\n"
                zep.thread.add_messages(thread_id=thread_id, messages=[Message(role="user", content=f"Uploaded: {txt}")])
            except: pass

    # GENERATE AI RESPONSE
    # If we transcribed audio, use the transcribed text as the user message
    if transcribed_text:
        user_msg = transcribed_text
    else:
        user_msg = text if text else "Processing..."
    
    try:
        model_name = "gemini-2.0-flash-exp"
        
        # STEP 2: Send the text (or transcribed text) to the AI for a real response
        resp = client.models.generate_content(
            model=model_name,
            contents=[types.Content(role="user", parts=[
                types.Part.from_text(text=f"{base_prompt}\nUSER INPUT: {user_msg}")
            ])],
            config=SAFETY_CONFIG
        )
        
        # STEP 3: Format the response
        if transcribed_text:
            # Audio input: show transcript + AI response
            final_response = f"🎤 [TRANSCRIPT]: {transcribed_text}\n\n{resp.text}"
        else:
            # Text input: just return AI response
            final_response = resp.text
            
        try:
            zep.thread.add_messages(thread_id=thread_id, messages=[
                Message(role="user", content=user_msg),
                Message(role="ai", content=resp.text)
            ])
        except: pass

        return {"response": final_response}

    except Exception as e:
        return {"response": f"Error: {str(e)}"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)