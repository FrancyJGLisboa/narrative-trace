"""Turn scenes into first-person prose: deterministic templates, optional guarded LLM."""
import json
import os
import urllib.request

from . import store
from .chunker import build_scenes
from .render import render_story
from .schema import truncate
from .validator import validate_scene

TITLES = {
    "mission": ("A missão", "The mission"),
    "investigate": ("Investigação", "Investigation"),
    "change": ("A mudança", "The change"),
    "setback": ("O tropeço", "Setback"),
    "verify": ("O veredito", "The verdict"),
    "run": ("Execução", "Running"),
    "closing": ("O desfecho", "Closing"),
    "other": ("Outras ações", "Other actions"),
}

T = {
    "pt": {
        "mission": 'Você me pediu: "{prompt}". Comecei a trabalhar nisso.',
        "investigate": "Fui investigar: consultei {targets}.",
        "change": "Alterei {targets}.",
        "setback": "Algo deu errado: {first_fact}.",
        "verify": "Rodei a verificação ({targets}) e ela passou.",
        "run": "Executei {targets}.",
        "closing_final": 'Terminei. Minhas palavras finais: "{final}"',
        "closing": "Terminei este turno.",
        "other": "Executei: {targets}.",
        "reason": ' O motivo que registrei: "{reason}"',
    },
    "en": {
        "mission": 'You asked me: "{prompt}". I started working on it.',
        "investigate": "I investigated: I looked at {targets}.",
        "change": "I changed {targets}.",
        "setback": "Something went wrong: {first_fact}.",
        "verify": "I ran the check ({targets}) and it passed.",
        "run": "I ran {targets}.",
        "closing_final": 'I finished. My final words: "{final}"',
        "closing": "I finished this turn.",
        "other": "I did: {targets}.",
        "reason": ' The reason I recorded: "{reason}"',
    },
}

SYSTEM = """You are the AI agent that performed the actions below. Narrate your own work to the human, in first person, in {LANG}.
Write ONE scene: 1 to 4 sentences of plain prose. No headings, no lists, no markdown.
Rules:
1. Use only the FACTS, TARGETS, REASONS, PROMPT and FINAL given. Add no other facts.
2. Write every file name, command and identifier exactly as given.
3. If REASONS is empty, do not explain why you did anything. Say only what happened.
4. Do not invent emotions or physical sensations. A setback is described as what failed and where.
5. Do not mention events that are not listed.
Output only the scene text."""


def lang():
    v = (os.environ.get("NT_LANG") or "pt").lower()
    return "en" if v.startswith("en") else "pt"


def title(phase, lg):
    pt, en = TITLES.get(phase, TITLES["other"])
    return en if lg == "en" else pt


def template_scene(scene, lg="pt"):
    t = T[lg]
    phase = scene["phase"]
    fill = {
        "prompt": truncate((scene.get("prompt") or "").strip(), 300),
        "final": truncate((scene.get("final") or "").strip(), 300),
        "targets": ", ".join(scene.get("targets") or []) or "-",
        "first_fact": (scene.get("facts") or ["?"])[0],
    }
    if phase == "closing":
        key = "closing_final" if scene.get("final") else "closing"
    elif phase == "verify" and scene.get("status") == "error":
        key = "setback"
    else:
        key = phase if phase in t else "other"
    text = t[key].format(**fill)
    if scene.get("reasons"):
        text += t["reason"].format(reason=truncate(scene["reasons"][0].strip(), 300))
    return text


def llm_enabled():
    return bool(os.environ.get("NT_LLM_URL") and os.environ.get("NT_LLM_MODEL"))


def http_call(system, user):
    url = os.environ["NT_LLM_URL"].rstrip("/") + "/chat/completions"
    body = json.dumps({
        "model": os.environ["NT_LLM_MODEL"], "temperature": 0.2, "max_tokens": 300,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    if os.environ.get("NT_LLM_KEY"):
        req.add_header("Authorization", "Bearer " + os.environ["NT_LLM_KEY"])
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def llm_scene(scene, prev_text, lg="pt", call=None):
    """Return (text, source). Falls back to the template on any failure."""
    call = call or http_call
    system = SYSTEM.replace("{LANG}", "English" if lg == "en" else "Brazilian Portuguese")
    payload = {k: scene.get(k) for k in
               ("phase", "facts", "targets", "reasons", "status", "prompt", "final")}
    payload["previous_scene_text"] = prev_text or ""
    user = json.dumps(payload, ensure_ascii=False)
    try:
        for attempt in range(2):
            text = (call(system, user) or "").strip()
            ok, why = validate_scene(text, scene, lg)
            if ok:
                return text, "llm"
            user = user + "\nYour previous answer was rejected: %s. Fix it." % why
    except Exception:
        pass
    return template_scene(scene, lg), "template_fallback"


def narrate_turn(d, turn, call=None):
    lg = lang()
    events = store.read_events(d, turn)
    if not events:
        return []
    scenes = build_scenes(events)
    path = os.path.join(d, "scenes.jsonl")
    with store.session_lock(d, timeout=30):
        existing = store.read_jsonl(path)
        keep = {(r["turn"], r["n"], tuple(r["seqs"])): r for r in existing}
        others = [r for r in existing if r.get("turn") != turn]
        rows, prev = [], ""
        for s in scenes:
            key = (turn, s["n"], tuple(s["seqs"]))
            if key in keep:
                row = keep[key]
            else:
                if llm_enabled() or call is not None:
                    text, src = llm_scene(s, prev, lg, call)
                else:
                    text, src = template_scene(s, lg), "template"
                row = {"turn": turn, "n": s["n"], "phase": s["phase"],
                       "title": title(s["phase"], lg), "text": text,
                       "seqs": s["seqs"], "source": src}
            rows.append(row)
            prev = row["text"]
        all_rows = sorted(others + rows, key=lambda r: (r["turn"], r["n"]))
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for r in all_rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(tmp, path)
        render_story(d)
    return rows


def narrate_all(d, call=None):
    turns = sorted({e.get("turn") for e in store.read_events(d) if e.get("turn")})
    out = []
    for t in turns:
        out += narrate_turn(d, t, call)
    return out
