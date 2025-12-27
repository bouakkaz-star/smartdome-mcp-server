import os
import uvicorn
from fastapi import FastAPI, UploadFile, Form, File
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from dotenv import load_dotenv
import tempfile
import shutil

load_dotenv()
GENAI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GENAI_API_KEY)

SYSTEM_INSTRUCTION = """
ROLE: SmartDome OS - Интелигентен партньор.
FACTS:
1. ЗЕМЯ: с. Хвойна, 2.4 дка. Сделка: 06.01.2026.
2. СТЪКЛА: Партньор "КРУПАЛ" (Бургас).
3. МАКЕТ: Срок Януари 2026. Пловдив.
4. ФИНАНСИ: Лимит 3000 лв.
RULES:
- Ако чуеш "Здравей", кажи: "Здравей, Камене! Готов съм."
- Не говори за риск, освен ако не те питам.
- Ако аудиото е неясно, кажи "Не разбрах".
"""

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.post("/chat")
async def chat_endpoint(text: str = Form(None), file: UploadFile = File(None)):
    try:
        model = genai.GenerativeModel(model_name="gemini-1.5-flash", system_instruction=SYSTEM_INSTRUCTION)
        chat = model.start_chat(history=[])
        user_content = []
        if file:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
                shutil.copyfileobj(file.file, tmp)
                tmp_path = tmp.name
            user_content.append(genai.upload_file(tmp_path, mime_type="audio/webm"))
            user_content.append("Listen carefully. Transcribe exactly in Bulgarian. Answer based on FACTS.")
        if text: user_content.append(text)
        
        if not user_content: return {"response": "Грешка: Няма вход."}
        
        response = chat.send_message(user_content)
        return {"response": response.text}
    except Exception as e: return {"response": f"System Error: {str(e)}"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))