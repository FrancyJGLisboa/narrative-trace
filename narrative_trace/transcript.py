"""Best-effort reader for Claude Code JSONL transcripts (agent text between tool calls)."""
import json


def _texts_from_content(content):
    if isinstance(content, str):
        return [content] if content.strip() else []
    out = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                t = block.get("text")
                if isinstance(t, str) and t.strip():
                    out.append(t.strip())
    return out


def read_new_assistant_texts(path, offset):
    """Return (texts, new_offset). Never raises."""
    if not path:
        return [], offset
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except (OSError, UnicodeDecodeError):
        return [], offset
    texts = []
    # If the transcript shrank (new file / compaction), restart from 0.
    start = offset if offset <= len(lines) else 0
    for line in lines[start:]:
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if not isinstance(obj, dict) or obj.get("type") != "assistant":
            continue
        msg = obj.get("message")
        if isinstance(msg, dict):
            texts.extend(_texts_from_content(msg.get("content")))
    return texts, len(lines)
