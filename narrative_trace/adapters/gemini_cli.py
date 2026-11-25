"""Gemini CLI hooks: BeforeAgent, AfterTool, AfterAgent."""
from . import agent_text, agent_words, tool_result, turn_end, turn_start

H = "gemini_cli"
EVENTS = ("BeforeAgent", "AfterTool", "AfterAgent")
STDOUT = {e: "{}" for e in EVENTS}  # Gemini CLI parses stdout as JSON


def to_events(event_name, payload, session, state):
    try:
        if event_name == "BeforeAgent":
            return [turn_start(H, session, payload)]
        if event_name == "AfterTool":
            return [tool_result(H, session, payload)]
        if event_name == "AfterAgent":
            last = agent_words(payload)
            out = [agent_text(H, session, last)] if last else []
            return out + [turn_end(H, session)]
    except Exception:
        return []
    return []
