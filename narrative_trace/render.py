"""Write story.md from scenes.jsonl (deterministic)."""
import os

from . import quiz, store


def _span(seqs):
    if not seqs:
        return ""
    if len(seqs) == 1:
        return "#%d" % seqs[0]
    return "#%d-#%d" % (seqs[0], seqs[-1])


def render_story(d):
    rows = sorted(store.read_jsonl(os.path.join(d, "scenes.jsonl")),
                  key=lambda r: (r.get("turn", 0), r.get("n", 0)))
    quizzes = {r["turn"]: r for r in store.read_jsonl(os.path.join(d, "quiz.jsonl"))}
    last_of = {}
    for r in rows:
        last_of[r.get("turn")] = r.get("n")
    session = os.path.basename(os.path.normpath(d))
    lines = ["# Narrative Trace: session %s" % session, ""]
    turn = None
    for r in rows:
        if r.get("turn") != turn:
            turn = r.get("turn")
            lines += ["## Turn %s" % turn, ""]
        lines.append("**Scene %s: %s**" % (r.get("n"), r.get("title")))
        lines.append(r.get("text", ""))
        if r.get("lesson"):
            lines.append("> " + r["lesson"])
        lines.append("<sub>events %s</sub>" % _span(r.get("seqs") or []))
        lines.append("")
        q = quizzes.get(r.get("turn"))
        if q and last_of.get(r.get("turn")) == r.get("n"):
            lines += quiz.render_block(q["items"], q.get("lang", "pt"))
    tmp = os.path.join(d, "story.md.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    os.replace(tmp, os.path.join(d, "story.md"))
    return os.path.join(d, "story.md")
