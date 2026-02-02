import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=API_KEY)

print("Listing models...")
with open("models.txt", "w") as f:
    try:
        models = list(client.models.list())
        for model in sorted(models, key=lambda x: x.name):
            msg = f"Model: {model.name} | Actions: {model.supported_actions}\n"
            print(msg, end="")
            f.write(msg)
    except Exception as e:
        f.write(f"Error: {e}\n")
        print(f"Error: {e}")
