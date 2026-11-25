"""Cursor hooks (observe-only events plus beforeSubmitPrompt)."""
from . import agent_text, agent_words, tool_result, turn_end, turn_start
from ..schema import pick

H = "cursor"
# Installed events. afterFileEdit/afterShellExecution are still understood if you add them
# yourself, but they duplicate postToolUse and carry no exit code, so they are not installed.
EVENTS = ("beforeSubmitPrompt", "postToolUse", "postToolUseFailure", "afterAgentResponse",
          "stop")
STDOUT = {"beforeSubmitPrompt": '{"continue": true}'}


def to_events(event_name, payload, session, state):
    try:
        if event_name == "beforeSubmitPrompt":
            return [turn_start(H, session, payload)]
        if event_name == "afterFileEdit":
            return [tool_result(H, session, payload, tool="Edit",
                                target=pick(payload, "file_path", "filePath", "path"))]
        if event_name == "afterShellExecution":
            return [tool_result(H, session, payload, tool="Shell",
                                target=pick(payload, "command", "cmd"))]
        if event_name in ("postToolUse", "postToolUseFailure"):
            return [tool_result(H, session, payload,
                                force_error=event_name == "postToolUseFailure")]
        if event_name == "afterAgentResponse":
            words = agent_words(payload)
            return [agent_text(H, session, words)] if words else []
        if event_name == "stop":
            return [turn_end(H, session)]
    except Exception:
        return []
    return []
