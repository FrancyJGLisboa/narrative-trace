"""Neutral event schema and small helpers shared by every adapter."""
import datetime as _dt
import re

KINDS = ("turn_start", "tool_call", "tool_result", "agent_text", "error", "turn_end")

_REDACT = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[=:]\s*\S+"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9._-]{16,}"),
]

SHELL_TOOLS = {"bash", "shell", "run_shell_command", "shell_command", "exec",
               "terminal", "local_shell", "exec_command", "run_terminal_cmd",
               "run_terminal_command", "powershell"}
_SHELL_HINTS = ("shell", "terminal", "bash", "powershell")
_READ_CMD = re.compile(
    r"^\s*(cat|head|tail|less|more|rg|grep|ag|ls|tree|find|fd|wc|stat|file|nl|"
    r"sed\s+-n|git\s+(diff|log|show|status|blame|grep))\b")
EXIT_RX = re.compile(r"(?i)(?:exit(?:ed)?\s*code|process exited with code)\s*:?\s*(-?\d+)")
_META = re.compile(r"(?i)^(command|directory|wall time|duration|exit code|process exited)\b")
_VERIFY = re.compile(
    r"\b(test|tests|pytest|jest|vitest|mocha|unittest|cargo test|go test|npm test|"
    r"pnpm test|yarn test|build|lint|tsc|mypy|ruff)\b")
_CHANGE = ("write", "edit", "patch", "replace", "create", "delete", "apply", "multiedit")
_INVESTIGATE = ("read", "grep", "glob", "search", "list", "ls", "find", "fetch", "web",
                "view", "open")


def now_iso():
    t = _dt.datetime.now(_dt.timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (t.microsecond // 1000)


def _get(d, key):
    cur = d
    for part in key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def pick(d, *keys, default=None):
    """First non-empty value among keys (dotted keys allowed). Never raises."""
    if not isinstance(d, dict):
        return default
    for k in keys:
        try:
            v = _get(d, k)
        except Exception:
            v = None
        if v not in (None, "", [], {}):
            return v
    return default


def truncate(s, n):
    if s is None:
        return None
    s = str(s)
    return s if len(s) <= n else s[: n - 3] + "..."


def redact(s):
    if s is None:
        return None
    s = str(s)
    for rx in _REDACT:
        s = rx.sub("[REDACTED]", s)
    return s


def as_text(v):
    """Turn any tool output / message shape into a flat string."""
    if v is None:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        parts = [as_text(x) for x in v]
        return " ".join(p for p in parts if p)
    if isinstance(v, dict):
        for k in ("text", "stderr", "error", "error_message", "message", "output", "stdout",
                  "llmContent", "returnDisplay", "content"):
            if v.get(k) not in (None, ""):
                return as_text(v[k])
        return None
    return str(v)


def extract_target(tool_input):
    if isinstance(tool_input, dict):
        v = pick(tool_input, "file_path", "path", "filePath", "absolute_path", "target_file", "command",
                 "cmd", "pattern", "query", "url", "notebook_path")
        if isinstance(v, list):
            v = " ".join(str(x) for x in v)
        return None if v is None else str(v)
    if isinstance(tool_input, str):
        return tool_input
    return None


def extract_change(tool_input):
    """Return {"before": str|None, "after": str} for edit-like tools, else None."""
    if not isinstance(tool_input, dict):
        return None
    edits = tool_input.get("edits")
    src = edits[0] if isinstance(edits, list) and edits and isinstance(edits[0], dict) else tool_input
    old = pick(src, "old_string", "oldString", "old_str", "old_text")
    new = pick(src, "new_string", "newString", "new_str", "new_text")
    if isinstance(new, str):
        return {"before": old if isinstance(old, str) and old else None, "after": new}
    body = pick(tool_input, "content", "file_text", "fileText")
    if isinstance(body, str) and extract_target(tool_input):
        return {"before": None, "after": body}
    return None


def _clip_change(change):
    if not change:
        return None
    out = {}
    for k in ("before", "after"):
        v = change.get(k)
        out[k] = truncate(redact(" ".join(v.split())), 160) if isinstance(v, str) else None
    return out if out["after"] is not None else None


def make_event(kind, harness, session, tool=None, target=None, status=None,
               error_text=None, text=None, change=None):
    target = truncate(redact(target), 200)
    if tool and target:
        summary = "%s %s" % (tool, target)
    else:
        summary = tool or target or kind
    if status == "error":
        short = summarize_error(error_text)
        if short:
            summary += ": " + short
    return {
        "v": 1, "seq": None, "ts": now_iso(), "session": session, "turn": None,
        "harness": harness, "kind": kind, "tool": tool, "target": target,
        "status": status, "summary": truncate(redact(summary), 300),
        "text": truncate(redact(text), 2000),
        "change": _clip_change(change),
    }


def is_shell(tool):
    tool = (tool or "").lower()
    return tool in SHELL_TOOLS or any(h in tool for h in _SHELL_HINTS)


def summarize_error(text):
    """One informative line from a tool error/output, plus the exit code if any."""
    if not text:
        return None
    text = str(text)
    m = EXIT_RX.search(text)
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or _META.match(line):
            continue
        line = re.sub(r"(?i)^(output|stdout|stderr)\s*:\s*", "", line).strip()
        if line and line not in ("(empty)", "(none)"):
            lines.append(line)
    pref = [x for x in lines if re.search(r"(?i)fail|error|exception|traceback|not found", x)]
    best = (pref or lines or [""])[0]
    if m and m.group(1) not in ("0",):
        best = (best + " (exit %s)" % m.group(1)).strip()
    return best or None


def classify_phase(event):
    tool = (event.get("tool") or "").lower()
    target = (event.get("target") or "").lower()
    if is_shell(tool):
        if _VERIFY.search(target):
            return "verify"
        return "investigate" if _READ_CMD.match(target) else "run"
    if any(k in tool for k in _CHANGE):
        return "change"
    if any(k in tool for k in _INVESTIGATE):
        return "investigate"
    return "other"
