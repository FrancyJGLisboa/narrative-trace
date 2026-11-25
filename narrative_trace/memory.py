"""Concepts a person has already met, kept per project so notes do not repeat in every session.

File: <stories folder>/concepts.json (next to the session folders).
{"edit": {"session": "<id>", "session_start": "<ISO ts>", "taught_at": "<ISO ts>"}, ...}
A concept counts as known in a session only if an EARLIER session taught it. So rebuilding a
session gives the same story as the first time.
"""
import json
import os

from .schema import now_iso

NAME = "concepts.json"


def _path(d):
    return os.path.join(os.path.dirname(os.path.abspath(d)), NAME)


def load(d):
    try:
        with open(_path(d), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def known_before(d, session_start):
    return {k for k, v in load(d).items()
            if isinstance(v, dict) and (v.get("session_start") or "") < (session_start or "")}


def remember(d, keys, session_start):
    if not keys:
        return
    mem = load(d)
    changed = False
    for k in keys:
        if k not in mem:
            mem[k] = {"session": os.path.basename(os.path.normpath(d)),
                      "session_start": session_start, "taught_at": now_iso()}
            changed = True
    if changed:
        p = _path(d)
        tmp = p + ".%d.tmp" % os.getpid()
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(mem, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, p)
