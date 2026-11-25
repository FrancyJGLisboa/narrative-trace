"""Group the events of one turn into scenes (deterministic)."""
from .schema import classify_phase

MAX_EVENTS = 8


def _scene(turn, phase):
    return {"turn": turn, "n": 0, "phase": phase, "seqs": [], "facts": [], "targets": [],
            "reasons": [], "status": "ok", "prompt": None, "final": None}


def _add(scene, ev):
    scene["seqs"].append(ev["seq"])
    if ev.get("summary"):
        scene["facts"].append(ev["summary"])
    t = ev.get("target")
    if t and t not in scene["targets"]:
        scene["targets"].append(t)
    if ev.get("status") == "error":
        scene["status"] = "error"


def build_scenes(events):
    scenes, open_scene, pending = [], None, []
    turn = events[0]["turn"] if events else 1

    def close():
        nonlocal open_scene
        if open_scene is not None:
            scenes.append(open_scene)
            open_scene = None

    def take_pending(scene):
        for seq, text in pending:
            scene["seqs"].append(seq)
            scene["reasons"].append(text)
        pending.clear()

    result_seqs = {e.get("seq") for e in events if e["kind"] == "tool_result"}
    for ev in events:
        kind = ev.get("kind")
        if kind == "turn_start":
            close()
            s = _scene(turn, "mission")
            s["prompt"] = ev.get("text")
            s["seqs"].append(ev["seq"])
            scenes.append(s)
        elif kind == "agent_text":
            if ev.get("text"):
                pending.append((ev["seq"], ev["text"]))
        elif kind in ("tool_result", "tool_call", "error"):
            if kind == "tool_call" and result_seqs:
                continue  # results carry the same information
            if kind == "error" or ev.get("status") == "error":
                close()
                s = _scene(turn, "setback")
                take_pending(s)
                _add(s, ev)
                s["status"] = "error"
                scenes.append(s)
                continue
            phase = classify_phase(ev)
            if (open_scene is not None and open_scene["phase"] == phase
                    and len(open_scene["seqs"]) < MAX_EVENTS and not pending):
                _add(open_scene, ev)
            else:
                close()
                open_scene = _scene(turn, phase)
                take_pending(open_scene)
                _add(open_scene, ev)
        elif kind == "turn_end":
            close()
            s = _scene(turn, "closing")
            if pending:
                s["final"] = pending[-1][1]
                s["reasons"] = [t for _, t in pending[:-1]]
                s["seqs"] = [q for q, _ in pending]
                pending.clear()
            s["seqs"].append(ev["seq"])
            scenes.append(s)
    close()
    if pending:  # turn still running: keep agent words visible
        s = _scene(turn, "closing")
        s["final"] = pending[-1][1]
        s["seqs"] = [q for q, _ in pending]
        scenes.append(s)
    for i, s in enumerate(scenes, 1):
        s["n"] = i
        s["seqs"].sort()
    return scenes
