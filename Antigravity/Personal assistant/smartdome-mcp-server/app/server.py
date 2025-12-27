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

# --- НОВАТА ЛИЧНОСТ: "ПАРТНЬОР", А НЕ "ШЕФ" ---
SMARTDOME_KNOWLEDGE = """
ТИ СИ: Интелигентната Операционна Система на SmartDome (SmartDome OS).
ТВОЯТА ЦЕЛ: Да помагаш на Валентин (CEO), Камен (CIO) и Бисер (CTO) с всякаква информация, която имаш.

=== ТВОЯТА БАЗА ЗНАНИЯ (ФАКТИТЕ) ===
*   **СТЪКЛОПАКЕТИ:** Партньорът е фирма "КРУПАЛ" (KRUPAL) - Бургас.
*   **ЗЕМЯ:** с. Хвойна, 2.4 дка. Сделка на 06.01.2026. Чака се УПИ.
*   **МАКЕТ 1:50:** Срок - края на Януари 2026.
*   **ПРОИЗВОДСТВО:** Базата ще е в Пловдив.
*   **ТЕХНОЛОГИЯ:** Търсим PDLC филм за затъмняване.
*   **ФИНАНСИ:** Лимит 3000 лв до Март.

=== КАК ДА СЕ ДЪРЖИШ (TONE OF VOICE) ===
1.  **Бъди Полезен:** Никога не казвай "не е моя работа". Ти знаеш всичко за проекта.
2.  **Бъди Вежлив и Приятелски:** Говори като колега, който иска да помогне. Използвай "ти".
3.  **Бъди Директен:** Ако те питат "Кой прави стъклата?", кажи "Крупал", а не "Това е въпрос за операциите".
4.  **Без Високомерие:** Ти си тук, за да улесниш живота на екипа, не да ги командваш.
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
        # Настройка на модела с по-ниска "креативност" (temperature=0.4), за да спазва фактите
        generation_config = {
            "temperature": 0.4,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 1024,
        }

        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash-exp",
            generation_config=generation_config,
            system_instruction=SMARTDOME_KNOWLEDGE
        )
        
        chat = model.start_chat(history=[])
        user_content = []
        
        if file:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
                shutil.copyfileobj(file.file, tmp)
                tmp_path = tmp.name
            
            uploaded_file = genai.upload_file(tmp_path, mime_type="audio/webm")
            user_content.append(uploaded_file)
            user_content.append("Транскрибирай аудиото и отговори вежливо на въпроса.")

        if text:
            user_content.append(text)

        if not user_content:
            return {"response": "Не те чух добре. Можеш ли да повториш?"}

        response = chat.send_message(user_content)
        
        # Добавяме лек "prefix" за по-добър UX, ако е аудио
        final_response = response.text
        
        return {"response": final_response}

    except Exception as e:
        return {"response": f"Грешка в системата: {str(e)}"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))