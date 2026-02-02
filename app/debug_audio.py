import os
import time
from pathlib import Path
from google import genai
from google.genai import types
from dotenv import load_dotenv

# 1. SETUP
BASE_DIR = Path(__file__).parent.parent.parent.parent
env_path = BASE_DIR / "smartdome-mcp-server" / ".env"

if env_path.exists():
    print(f"✅ Loading ENV from: {env_path}")
    load_dotenv(env_path)
else:
    print(f"❌ ENV NOT FOUND at: {env_path}")

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("❌ NO GEMINI_API_KEY FOUND")
    exit(1)

client = genai.Client(api_key=API_KEY)
TEMP_DIR = BASE_DIR / "apps" / "server" / "data" / "uploads"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# 2. CREATE DUMMY AUDIO (WEBM)
# Since we can't easily record audio here, we'll try to download one or create a text file mimicking it
# Actually, Gemini might reject a fake WEBM.
# Let's try to upload a text file first to verify the PIPELINE.
test_file = TEMP_DIR / "debug_test.txt"
with open(test_file, "w") as f:
    f.write("This is a test file to verify Gemini Uploads.")

print(f"📁 Created test file: {test_file}")

# 3. UPLOAD FUNCTION (Replicating main.py)
def test_upload(path, mime):
    print(f"🚀 Uploading {path} as {mime}...")
    try:
        # Try 'path' arg first
        try:
            up_file = client.files.upload(path=path, config=types.UploadFileConfig(mime_type=mime))
            print(f"✅ Success (path arg): {up_file.uri}")
            return up_file.uri
        except TypeError:
            print("⚠️ 'path' arg failed, trying 'file'...")
            up_file = client.files.upload(file=path, config=types.UploadFileConfig(mime_type=mime))
            print(f"✅ Success (file arg): {up_file.uri}")
            return up_file.uri
            
    except Exception as e:
        print(f"❌ Upload Failed: {e}")
        import traceback
        traceback.print_exc()
        return None

# 4. EXECUTE
uri = test_upload(test_file, "text/plain")

if uri:
    print("🧠 Generating Content...")
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_uri(file_uri=uri, mime_type="text/plain"),
                        types.Part.from_text(text="What does this file say?")
                    ]
                )
            ]
        )
        print(f"🤖 RESPONSE: {response.text}")
    except Exception as e:
        print(f"❌ Generation Failed: {e}")
else:
    print("❌ Skipping generation due to upload failure.")
