"""Replay a bundled example session through the real hook command."""
import json
import os
import subprocess
import sys

EXAMPLES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples")
LAUNCHER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "launcher.py")


def _subst(obj, mapping):
    if isinstance(obj, str):
        for k, v in mapping.items():
            obj = obj.replace(k, v)
        return obj
    if isinstance(obj, list):
        return [_subst(x, mapping) for x in obj]
    if isinstance(obj, dict):
        return {k: _subst(v, mapping) for k, v in obj.items()}
    return obj


def iter_payloads(harness, workdir):
    """Yield (event, payload) and keep the fake transcript growing in real time."""
    src = os.path.join(EXAMPLES, harness)
    tlines = []
    tpath = os.path.join(workdir, "transcript.jsonl")
    if os.path.exists(os.path.join(src, "transcript.jsonl")):
        with open(os.path.join(src, "transcript.jsonl"), encoding="utf-8") as f:
            tlines = f.readlines()
    mapping = {"{CWD}": workdir, "{TRANSCRIPT}": tpath}
    with open(os.path.join(src, "payloads.jsonl"), encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if isinstance(row.get("transcript_upto"), int):
                with open(tpath, "w", encoding="utf-8") as t:
                    t.writelines(tlines[: row["transcript_upto"]])
            yield row["event"], _subst(row["payload"], mapping)


def run_hook(harness, event, payload, env=None, timeout=30):
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run([sys.executable, LAUNCHER, "hook", "--harness", harness, "--event", event],
                          input=json.dumps(payload), capture_output=True, text=True,
                          env=e, timeout=timeout)


def replay(harness, workdir, env=None):
    """Run every example payload through the hook CLI. Returns the session dir."""
    workdir = os.path.abspath(workdir)
    os.makedirs(workdir, exist_ok=True)
    env = dict(env or {})
    env.setdefault("NT_SYNC", "1")
    env.pop("NT_HOME", None)
    sid = None
    for event, payload in iter_payloads(harness, workdir):
        run_hook(harness, event, payload, env)
        sid = payload.get("session_id") or payload.get("conversation_id") or sid
    return os.path.join(workdir, ".narrative", sid or "default")


def run_demo(harness, out):
    d = replay(harness, out)
    path = os.path.join(d, "story.md")
    with open(path, encoding="utf-8") as f:
        sys.stdout.write(f.read() + "\n")
    return path
