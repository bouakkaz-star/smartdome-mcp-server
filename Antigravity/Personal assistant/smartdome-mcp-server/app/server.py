import os
import uvicorn
from fastapi import FastAPI, UploadFile, Form, File
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from dotenv import load_dotenv
import tempfile
import shutil

# 1. Зареждане на средата
load_dotenv()
GENAI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GENAI_API_KEY:
    print("❌ ERROR: GEMINI_API_KEY липсва!")

genai.configure(api_key=GENAI_API_KEY)

# 2. КОНСТИТУЦИЯТА НА SMARTDOME (Това е паметта)
SMARTDOME_KNOWLEDGE = """
ТИ СИ: Виртуалният CEO на SmartDome. 
ТВОЯТА ЦЕЛ: Да даваш точни, кратки и експертни отговори на екипа.

=== ФАКТИТЕ (ТОВА Е ИСТИНАТА - НЕ ПИТАЙ, А ОТГОВАРЯЙ) ===
*   **СТЪКЛОПАКЕТИ:** Партньорът е фирма **"КРУПАЛ" (KRUPAL)** от Бургас.
*   **ЗЕМЯ:** с. Хвойна, 2.4 декара. Сделка на 06.01.2026. Чака се УПИ.
*   **МАКЕТ:** Трябва да е готов до края на Януари 2026.
*   **ПРОИЗВОДСТВО:** Базата ще е в Пловдив. Отговорник: Бисер.
*   **ТЕХНОЛОГИЯ:** Търсим PDLC Smart Glass филм (затъмняване).
*   **ФИНАНСИ:** Лимит до Март: 3000 лв. Одобрение само от Валентин.

=== ПРАВИЛА ЗА ПОВЕДЕНИЕ ===
1.  Ако те питат факт (напр. "Кой прави стъклата?"), ОТГОВОРИ ВЕДНАГА с факта ("Крупал"). НЕ задавай въпроси обратно.
2.  Говори на "ТИ". Бъди кратък.
3.  Не използвай шаблони като "[X] лева".
"""

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/chat")
async def chat_endpoint(text: str = Form(None), file: UploadFile = File(None)):
    try:
        # ТУК Е МАГИЯТА: system_instruction е по-силно от всичко
        model = genai.GenerativeModel(
            "gemini-2.0-flash-exp",
            system_instruction=SMARTDOME_KNOWLEDGE
        )
        
        # Стартираме празен чат - знанието вече е в "system_instruction"
        chat = model.start_chat(history=[])

        user_content = []
        
        # Аудио/Файл логика
        if file:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
                shutil.copyfileobj(file.file, tmp)
                tmp_path = tmp.name
            
            uploaded_file = genai.upload_file(tmp_path, mime_type="audio/webm")
            # Инструкция към аудиото
            user_content.append(uploaded_file)
            user_content.append("Транскрибирай това аудио и отговори на въпроса в него, използвайки знанията си за SmartDome.")

        # Текст логика
        if text:
            user_content.append(text)

        if not user_content:
            return {"response": "Не чух нищо. Моля, повтори."}

        response = chat.send_message(user_content)
        return {"response": response.text}

    except Exception as e:
        return {"response": f"Грешка в мозъка: {str(e)}"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))