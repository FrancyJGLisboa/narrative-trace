"""Deterministic fidelity checks for LLM-written scenes."""
import os
import re

PATH_RX = re.compile(
    r"(?:[\w-]+/)+[\w.-]+|\b[\w-]+\.(?:py|ts|tsx|js|jsx|json|md|rs|go|java|rb|css|html|"
    r"yml|yaml|toml|sql|sh|txt)\b")
CAUSAL = {
    "pt": ("porque", "pois", "já que", "por isso"),
    "en": ("because", "since", "so that", "therefore"),
}
MAX_LEN = 700


def _corpus(scene):
    parts = list(scene.get("facts") or []) + list(scene.get("targets") or [])
    parts += list(scene.get("reasons") or [])
    parts += [scene.get("prompt") or "", scene.get("final") or ""]
    for c in scene.get("changes") or []:
        parts += [c.get("before") or "", c.get("after") or ""]
    return "\n".join(str(p) for p in parts)


def validate_scene(text, scene, lang="pt"):
    if not isinstance(text, str) or not text.strip():
        return False, "empty answer"
    t = text.strip()
    if len(t) > MAX_LEN:
        return False, "longer than %d characters" % MAX_LEN
    for line in t.splitlines():
        s = line.lstrip()
        if s[:1] in ("-", "*", "#") or re.match(r"\d+\.", s):
            return False, "use plain prose, not lists or headings"
    corpus = _corpus(scene)
    for tok in PATH_RX.findall(t):
        tok = tok.rstrip(".")
        if tok and tok not in corpus:
            return False, "mentions %s, which is not in the events" % tok
    targets = scene.get("targets") or []
    if targets:
        names = [os.path.basename(x.rstrip("/")) or x for x in targets]
        if not any(n and n in t for n in names) and not any(x in t for x in targets):
            return False, "must name at least one of: %s" % ", ".join(targets[:5])
    if not scene.get("reasons"):
        low = t.lower()
        # The agent's own quoted final words may contain causal words.
        final = (scene.get("final") or "").lower()
        prompt = (scene.get("prompt") or "").lower()
        for w in CAUSAL.get(lang, CAUSAL["en"]):
            if re.search(r"\b%s\b" % re.escape(w), low) and w not in final and w not in prompt:
                return False, "explains why ('%s') but no reason was recorded" % w
    return True, ""
