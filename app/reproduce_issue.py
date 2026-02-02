
import os
import time
from pathlib import Path
from google import genai
from google.genai import types
from dotenv import load_dotenv

# SETUP
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
env_path = BASE_DIR / "smartdome-mcp-server" / ".env"
load_dotenv(env_path)
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# 1. CREATE DUMMY WEBM (Text disguised as WEBM or just empty)
# Gemini usually accepts empty files if we just need URI, but let's try 1kb random data
test_file = Path("test_audio.webm")
with open(test_file, "wb") as f:
    f.write(os.urandom(1024)) # 1KB random data

print(f"📁 Created {test_file}")

# 2. UPLOAD (As video/webm due to main.py logic)
print("🚀 Uploading as video/webm...")
try:
    up_file = client.files.upload(path=test_file, config=types.UploadFileConfig(mime_type="video/webm"))
    print(f"✅ Upload Success: {up_file.uri}")
    uri = up_file.uri
except Exception as e:
    print(f"❌ Upload Failed: {e}")
    exit(1)

# 3. CONSTRUCT PROMPT (Mimic main.py logic)
parts = []

# Part 1: File
# Note: main.py uses 'video/webm' mime for the Part too
parts.append(types.Part.from_uri(file_uri=uri, mime_type="video/webm"))

# Part 2: System Instructions (Mimic 'ext' check)
base_prompt = "You are an AI."
ext = ".webm"
audio_exts = [".webm", ".weba", ".mp3", ".wav", ".ogg", ".m4a", ".aac"]

if ext in audio_exts:
    print("✅ Extension Check Passed: Adding Audio Instruction.")
    base_prompt += "\n[SYSTEM]: Audio file attached. Transcribe the speech. User speaks BULGARIAN."
else:
    print("❌ Extension Check Failed.")

parts.append(types.Part.from_text(text=base_prompt))

print(f"🔢 Parts Count: {len(parts)}")

# 4. GENERATE
print("🧠 Generating...")
try:
    resp = client.models.generate_content(
        model="gemini-2.0-flash-exp", 
        contents=[types.Content(role="user", parts=parts)]
    )
    print(f"🤖 RESPONSE: {resp.text}")
except Exception as e:
    print(f"❌ Generation Failed: {e}")
