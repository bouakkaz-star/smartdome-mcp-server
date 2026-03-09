"""
Output Guard — SmartDome OS v6
================================
Post-processing filter applied to agent outputs before returning to user.
Enforces: banned words, style guide compliance, constraint violations.

Usage:
    from tools.output_guard import guard_output
    cleaned = guard_output(text, agent_id, participant_id)
"""
import re
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger("HAP-Guard")

# Style Guide v1_concise — banned words and phrases
BANNED_WORDS = [
    "utilize", "leverage", "delve", "facet", "tapestry",
    "testament", "realm", "seamless", "robust", "transformative",
]

BANNED_PHRASES = [
    "I hope this helps",
    "Let me know if you need anything else",
    "Let me know",
    "Here is the report you asked for",
    "Here's what I found",
    "I'd be happy to help",
    "Great question",
    "That's a great question",
]

# Agent-specific constraints
AGENT_CONSTRAINTS = {
    "ceo": {
        "banned_patterns": [
            r"\bwe\b(?!\s+(the company|SmartDome|as a company))",  # "we" only for company entity
        ],
        "required_greeting": "Ops Director online",
        "no_ralf_mention": True,  # CEO must not interact with RALF
    },
    "cto": {
        "no_hallucinate": True,  # Must cite sources for technical data
    },
}


def guard_output(
    text: str,
    agent_id: str = "unknown",
    participant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Apply output guards to agent response text.

    Args:
        text: The raw agent output.
        agent_id: Which agent produced this.
        participant_id: Which human is receiving this.

    Returns:
        dict with:
            text: Cleaned output text.
            violations: List of detected violations (for logging).
            cleaned: Whether any changes were made.
    """
    violations = []
    cleaned_text = text

    # 1. BANNED WORDS (case-insensitive replacement)
    for word in BANNED_WORDS:
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        if pattern.search(cleaned_text):
            violations.append(f"Banned word: '{word}'")
            # Replace with simpler alternatives
            replacements = {
                "utilize": "use", "leverage": "use", "delve": "explore",
                "facet": "aspect", "tapestry": "system", "testament": "proof",
                "realm": "area", "seamless": "smooth", "robust": "strong",
                "transformative": "significant",
            }
            replacement = replacements.get(word.lower(), "")
            if replacement:
                cleaned_text = pattern.sub(replacement, cleaned_text)

    # 2. BANNED PHRASES (case-insensitive removal)
    for phrase in BANNED_PHRASES:
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        if pattern.search(cleaned_text):
            violations.append(f"Banned phrase: '{phrase}'")
            cleaned_text = pattern.sub("", cleaned_text)

    # 3. AGENT-SPECIFIC CONSTRAINTS
    constraints = AGENT_CONSTRAINTS.get(agent_id.lower(), {})

    if constraints.get("no_ralf_mention"):
        ralf_pattern = re.compile(r"\bRALF\b", re.IGNORECASE)
        ralf_mentions = ralf_pattern.findall(cleaned_text)
        if ralf_mentions:
            violations.append(f"CEO mentioned RALF {len(ralf_mentions)} times — routing violation")

    # 4. CLEAN UP TOOL ARTIFACTS (BUG #3, #4, #8 FIX — v6.1)
    # Remove [TOOL] blocks, raw JSON, file paths, system logs, CLI errors
    tool_patterns = [
        (r'\[TOOL\][\s\S]*?\[/TOOL\]', 'TOOL block'),           # [TOOL]...[/TOOL] blocks
        (r'\[TOOL\][^\n]*', 'TOOL line'),                         # Single-line [TOOL] output
        (r'\[SYSTEM_LOG\][^\n]*', 'SYSTEM_LOG'),                  # System log entries
        (r'\[DELEGATE_TO:\s*\w+\]', 'DELEGATE marker'),          # Delegation markers
        (r'\[TRANSCRIPT\]:\s*[^\n]*', 'TRANSCRIPT marker'),      # Transcript markers
        (r'```json\s*\{[\s\S]*?\}[\s\S]*?```', 'JSON block'),   # JSON code blocks with tool data
        (r'[A-Z]:\\(?:Users|Windows|Program)[^\n]*', 'Windows path'),  # Windows file paths
        (r'/(?:home|tmp|var|usr|app)/[^\s\n]+', 'Unix path'),    # Unix file paths
        (r'\{"(?:tool_name|function_call|action|name)"[^\}]*\}', 'tool JSON'),  # Raw tool JSON
        (r'(?:Error|Exception|Traceback)[^\n]*(?:git|npm|pip|python|ffmpeg)[^\n]*', 'CLI error'),  # CLI errors
        (r'(?:^|\n)\s*File "[^"]+", line \d+[^\n]*', 'Python traceback'),  # Python tracebacks
    ]
    for pattern, label in tool_patterns:
        matches = re.findall(pattern, cleaned_text, re.MULTILINE)
        if matches:
            violations.append(f"Tool artifact [{label}]: {len(matches)} removed")
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.MULTILINE)

    # 5. CLEAN UP WHITESPACE
    cleaned_text = re.sub(r'  +', ' ', cleaned_text)
    cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
    cleaned_text = cleaned_text.strip()

    if violations:
        logger.info(f"Guard [{agent_id}]: {len(violations)} violations — {', '.join(violations[:3])}")

    return {
        "text": cleaned_text,
        "violations": violations,
        "cleaned": len(violations) > 0,
        "agent_id": agent_id,
    }
