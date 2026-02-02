import os

env_path = r"c:\Users\USER\Desktop\Antigravity\Personal assistant\smartdome-mcp-server\.env"

try:
    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Simple heuristic to fix merged lines (e.g. KEY=VALZEP_API_KEY=...)
    # We replace "ZEP_API_KEY" with "\nZEP_API_KEY" just in case.
    fixed_content = content.replace("ZEP_API_KEY=", "\nZEP_API_KEY=")
    
    # Also ensure Gemini key is on its own line if it got merged logic reversed
    fixed_content = fixed_content.replace("GEMINI_API_KEY=", "\nGEMINI_API_KEY=")
    fixed_content = fixed_content.replace("NOTION_API_KEY=", "\nNOTION_API_KEY=")
    
    # Clean up multiple newlines
    lines = [line.strip() for line in fixed_content.split('\n') if line.strip()]
    final_content = '\n'.join(lines)
    
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(final_content)
        
    print("ENV FIXED. Content:")
    print(final_content)

except Exception as e:
    print(f"Error: {e}")
