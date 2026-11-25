"""Codex CLI hooks: UserPromptSubmit, PostToolUse, Stop."""
from . import agent_text, agent_words, tool_result, turn_end, turn_start

H = "codex"
EVENTS = ("UserPromptSubmit", "PostToolUse", "Stop")
STDOUT = {"Stop": "{}"}  # Codex requires JSON on Stop


def to_events(event_name, payload, session, state):
    try:
        if event_name == "UserPromptSubmit":
            return [turn_start(H, session, payload)]
        if event_name == "PostToolUse":
            return [tool_result(H, session, payload)]
        if event_name == "Stop":
            last = agent_words(payload)
            out = [agent_text(H, session, last)] if last else []
            return out + [turn_end(H, session)]
    except Exception:
        return []
    return []
