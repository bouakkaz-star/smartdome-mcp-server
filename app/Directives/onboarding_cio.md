# CIO Technical Manual (SmartDome OS V3)
**Authorized Personnel Only: Kamen (CIO)**

## 1. System Architecture
The "Brain" of the OS is decoupled from the code.
- **Logic:** `app/tools/chat_tool.py` (The Engine)
- **Personality/Rules:** `app/Prompts/*.md` (The Soul)

## 2. Maintenance Tasks
### Updating the "Algorithm"
If you want to change HOW the agents think (e.g., "Use the Pyramid Principle"), do **NOT** touch the Python code.
1.  Open `app/Prompts/methodology.md`.
2.  Edit the text in plain English.
3.  Save. Behavior updates instantly for all agents.

### Adding a New Agent
1.  Open `app/tools/chat_tool.py`.
2.  Add a new key to the `AGENT_PERSONAS` dictionary.
3.  Ensure you include the `{METHODOLOGY}` formatting string.

## 3. "Omniscience" Mode
As CIO, you have full view.
- **Logs:** Check `app/logs/` (if enabled) or the Zep Cloud dashboard.
- **SOP Extraction:** Monitor `SOP` tags in the chat to see what the agents are learning.

## 4. Troubleshooting
- **API Errors:** Check `.env` for `GEMINI_API_KEY` and `ZEP_API_KEY`.
- **Hallucinations:** If an agent lies, update `criteria.md` with a stricter rule (e.g., "Violent Constraint: Never invent prices for land in Hvoyna").
