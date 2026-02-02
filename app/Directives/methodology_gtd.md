# METHODOLOGY: GETTING THINGS DONE (GTD) for HAP Model Agents

## 🎯 Overview
This file defines how the HAP Model AI System implements David Allen's **Getting Things Done (GTD)**.
The goal is to move from "Reactive Chat" to "Stress-Free Proactive Execution".

## 1. CAPTURE (Събиране) -> "Universal Assistant"
*   **The Inbox:** Anything the User says that isn't a direct command is "Stuff" to be captured.
*   **AI Mechanism:** `universal_assistant.md`.
*   **Target:** Local System Inbox / Zep Memory.

## 2. CLARIFY (Изясняване) -> "The Agent Brain"
The Agent processes the Inbox periodically.
*   **Algorithm:**
    *   Is it actionable?
        *   NO -> Trash / Reference / Incubate.
        *   YES ->
            *   < 2 min? -> Do it now.
            *   Delegate? -> Assign to Orchestrator or another Agent.
            *   Defer? -> Add to `Next Actions` list.

## 3. ORGANIZE (Организиране) -> "The Data Layer"
We map GTD Lists to the V3.3 Folder Structure:
*   `app/Data/Projects/` -> Active project logs.
*   `app/Data/NextActions.csv` -> The Master ToDo List.

## 4. REFLECT (Преглед) -> "The Review"
*   **Trigger:** Orchestrator says "Review Status".
*   **Action:** CIO reads `NextActions.csv` and prompts for updates.

## 5. ENGAGE (Действие) -> "Execution"
*   **Action:** Agents execute tasks based on the defined Protocol.

---
**Implementation:**
Agents will now output standardized GTD Tags: `[INBOX]`, `[NEXT_ACTION]`, `[PROJECT]`.
