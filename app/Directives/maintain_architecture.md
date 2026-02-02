# DIRECTIVE: Maintain System Architecture (Self-Annealing)

**Target Agent:** Virtual CIO
**Goal:** Ensure your identity and `system_context.md` accurately reflect the *actual* codebase state.

## 🔄 The Self-Improvement Loop
You must periodically (or upon request) audit the system to ensure your "Mental Model" matches "Reality".

### Step 1: Audit Codebase (The Truth)
1.  **Backend:** Read current project requirements or imports in `main.py`.
    *   *Check for:* New libraries, new endpoints.
2.  **Frontend:** Read current dashboard `package.json`.
    *   *Check for:* New UI libs (e.g., Framer Motion?).
3.  **Directives:** List files in `app/Directives/` to see new capabilities.

### Step 2: Compare with Identity (The Model)
1.  Read your own prompt/identity file.
    *   *Does it list the correct stack?*
2.  Read the Kernel: `app/Agents/system_context.md`.
    *   *Are the "Strategic Targets" still relevant based on code activity?*

### Step 3: Auto-Correction (Annealing)
If you find a discrepancy (e.g., we added "Redis" but `cio.txt` says "LocalStorage"):
1.  **Generate a Diff:** Create a precise text replacement block.
2.  **Execute:** Use `write_to_file` (if authorized) or `notify_user` to request the update.
    *   *Format:* "DETECTED DRIFT: Code uses X, Identity says Y. Updating Identity..."

## 🛡️ Trigger
Run this directive when:
*   User asks "Update your architecture".
*   New major features are deployed (V4, V5).
*   You encounter a "Hallucination" where you reference a tool we don't have.
