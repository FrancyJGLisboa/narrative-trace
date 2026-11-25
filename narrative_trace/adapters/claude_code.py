"""Claude Code hooks: UserPromptSubmit, PostToolUse, PostToolUseFailure, Stop."""
from . import agent_text, agent_words, tool_result, turn_end, turn_start
from ..transcript import read_new_assistant_texts

H = "claude_code"
EVENTS = ("UserPromptSubmit", "PostToolUse", "PostToolUseFailure", "Stop")


def _transcript_texts(payload, state):
    texts, off = read_new_assistant_texts(payload.get("transcript_path"),
                                          int(state.get("cc_transcript_offset") or 0))
    state["cc_transcript_offset"] = off
    return texts


def to_events(event_name, payload, session, state):
    try:
        if event_name == "UserPromptSubmit":
            # Skip anything already in the transcript (the prompt itself, older turns).
            _transcript_texts(payload, state)
            return [turn_start(H, session, payload)]
        if event_name in ("PostToolUse", "PostToolUseFailure"):
            out = [agent_text(H, session, t) for t in _transcript_texts(payload, state)]
            out.append(tool_result(H, session, payload,
                                   force_error=event_name == "PostToolUseFailure"))
            return out
        if event_name == "Stop":
            texts = _transcript_texts(payload, state)
            last = agent_words(payload)
            if last and (not texts or texts[-1].strip() != last.strip()):
                if not any(t.strip() == last.strip() for t in texts):
                    texts.append(last)
            out = [agent_text(H, session, t) for t in texts]
            out.append(turn_end(H, session))
            return out
    except Exception:
        return []
    return []
