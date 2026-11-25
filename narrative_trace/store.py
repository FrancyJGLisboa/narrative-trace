"""Per-session storage: trace.jsonl, state.json, scenes.jsonl, story.md."""
import contextlib
import json
import os
import re
import time

from .schema import pick

DEFAULT_STATE = {"current_turn": 0, "last_seq": 0, "cc_transcript_offset": 0,
                 "narrated_turns": []}


def session_id(payload):
    sid = pick(payload, "session_id", "sessionId", "conversation_id", "conversationId",
               "thread_id", "threadId") or "default"
    sid = re.sub(r"[^A-Za-z0-9_-]", "_", str(sid))[:64]
    return sid or "default"


def project_dir(payload):
    p = pick(payload, "cwd")
    if not p:
        roots = pick(payload, "workspace_roots")
        if isinstance(roots, list) and roots:
            p = roots[0]
    return p or os.getcwd()


def session_dir(payload):
    base = os.environ.get("NT_HOME") or os.path.join(project_dir(payload), ".narrative")
    d = os.path.join(base, session_id(payload))
    os.makedirs(d, exist_ok=True)
    return d


@contextlib.contextmanager
def session_lock(d, timeout=3.0, stale=10.0):
    path = os.path.join(d, "lock")
    start = time.time()
    fd = None
    while fd is None:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(path) > stale:
                    os.remove(path)
                    continue
            except OSError:
                pass
            if time.time() - start > timeout:
                raise TimeoutError("could not acquire " + path)
            time.sleep(0.02)
    try:
        yield
    finally:
        os.close(fd)
        try:
            os.remove(path)
        except OSError:
            pass


def load_state(d):
    state = dict(DEFAULT_STATE)
    state["narrated_turns"] = []
    try:
        with open(os.path.join(d, "state.json"), encoding="utf-8") as f:
            state.update(json.load(f))
    except (OSError, ValueError):
        pass
    return state


def save_state(d, state):
    tmp = os.path.join(d, "state.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(tmp, os.path.join(d, "state.json"))


def append_events(d, events, state_updates=None):
    """Assign seq/turn and append, all under one lock. Returns stored events."""
    out = []
    with session_lock(d):
        state = load_state(d)
        if state_updates:
            state.update(state_updates)
        with open(os.path.join(d, "trace.jsonl"), "a", encoding="utf-8") as f:
            for ev in events:
                if ev["kind"] == "turn_start":
                    state["current_turn"] += 1
                ev["turn"] = max(1, state["current_turn"])
                state["last_seq"] += 1
                ev["seq"] = state["last_seq"]
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
                out.append(ev)
        save_state(d, state)
    return out


def append_event(d, event):
    return append_events(d, [event])[0]


def read_jsonl(path):
    rows = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return rows


def read_events(d, turn=None):
    evs = [e for e in read_jsonl(os.path.join(d, "trace.jsonl")) if isinstance(e, dict)]
    if turn is not None:
        evs = [e for e in evs if e.get("turn") == turn]
    return sorted(evs, key=lambda e: e.get("seq") or 0)


def log_error(d, text):
    try:
        with open(os.path.join(d, "errors.log"), "a", encoding="utf-8") as f:
            f.write(text.rstrip() + "\n")
    except OSError:
        pass
