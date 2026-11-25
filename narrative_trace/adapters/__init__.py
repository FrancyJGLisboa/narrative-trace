"""Harness adapters: native hook payload -> neutral events."""
import json

from ..schema import EXIT_RX, as_text, extract_change, extract_target, is_shell, make_event, pick, truncate

TOOL_NAME = ("tool_name", "toolName", "tool")
TOOL_INPUT = ("tool_input", "toolInput", "input", "args", "arguments")
TOOL_OUTPUT = ("tool_response", "toolResponse", "tool_output", "output", "result")
PROMPT = ("prompt", "user_prompt", "userPrompt", "text", "message")
AGENT = ("last_assistant_message", "prompt_response", "response", "text", "thought", "message")


def _nonzero(v):
    try:
        return v is not None and int(v) != 0
    except (TypeError, ValueError):
        return False


def _maybe_json(v):
    if isinstance(v, str) and v.strip()[:1] in ("{", "["):
        try:
            return json.loads(v)
        except ValueError:
            return v
    return v


def tool_status(payload, tool=None):
    """Return (status, error_text)."""
    out = _maybe_json(pick(payload, *TOOL_OUTPUT))
    err = pick(payload, "error", "tool_error", "error_message", "errorMessage")
    failed = bool(err)
    if isinstance(out, dict):
        if out.get("is_error") is True or out.get("isError") is True or out.get("success") is False:
            failed = True
        if _nonzero(out.get("exit_code")) or _nonzero(out.get("exitCode")):
            failed = True
        if out.get("error"):
            failed = True
            err = err or out.get("error")
    if _nonzero(payload.get("exit_code")) or _nonzero(payload.get("exitCode")):
        failed = True
    if not failed and is_shell(tool or pick(payload, *TOOL_NAME)):
        m = EXIT_RX.search((as_text(out) or "")[:4000])
        if m and _nonzero(m.group(1)):
            failed = True
    if not failed:
        return "ok", None
    text = as_text(err) or pick(payload, "stderr") or as_text(out) or "error"
    return "error", truncate(str(text).strip(), 2000)


def tool_result(harness, session, payload, tool=None, target=None, force_error=False):
    tool = tool or pick(payload, *TOOL_NAME)
    tool_input = pick(payload, *TOOL_INPUT)
    if target is None:
        target = extract_target(tool_input)
    status, err = tool_status(payload, tool)
    if force_error and status != "error":
        status = "error"
        err = as_text(pick(payload, "error", "error_message", *TOOL_OUTPUT)) or "error"
    return make_event("tool_result", harness, session, tool=tool, target=target,
                      status=status, error_text=err,
                      change=extract_change(tool_input) if status != "error" else None)


def turn_start(harness, session, payload):
    return make_event("turn_start", harness, session, text=as_text(pick(payload, *PROMPT)))


def agent_text(harness, session, text):
    return make_event("agent_text", harness, session, text=text)


def turn_end(harness, session):
    return make_event("turn_end", harness, session)


def agent_words(payload):
    return as_text(pick(payload, *AGENT))


def get_adapter(name):
    from . import claude_code, codex, cursor, gemini_cli, generic
    table = {"claude_code": claude_code, "codex": codex, "gemini_cli": gemini_cli,
             "cursor": cursor, "generic": generic}
    if name not in table:
        raise ValueError("unknown harness: %s (choose: %s)" % (name, ", ".join(table)))
    return table[name]


HARNESSES = ("claude_code", "codex", "gemini_cli", "cursor", "generic")
