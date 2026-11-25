"""Practice mode: ask the quiz in the terminal, log confidence and result, report weak spots.

narrative-trace quiz            answer the open questions of the latest session
narrative-trace quiz --report   see where you were sure and wrong

Log: <stories folder>/scores.jsonl, one line per answer. Self-graded: you see the answer and say if you got it.
"""
import json
import os

from .schema import now_iso
from . import store

T = {
    "pt": {
        "conf": "Quanta certeza você tem? 1 = chute, 2 = talvez, 3 = certeza: ",
        "ans": "Escreva sua resposta (Enter para pular): ", "right": "Resposta certa: ",
        "ok": "Você acertou? (s/n): ", "none": "Nenhuma pergunta aberta.", "done": "Registrado em ",
        "head": "Painel de prática", "total": "Respostas: {n}. Acertos: {p}%.",
        "bycf": "Por certeza (leia assim: com certeza 3, o acerto deve ser alto):",
        "cf": "  certeza {c}: {n} respostas, {p}% de acertos",
        "sure": "Certeza 3 e errou (aqui o equívoco está escondido):", "nosure": "Nenhum erro com certeza 3.",
        "kinds": "Por tema (aprendido = 2 acertos seguidos):", "learned": "aprendido", "open": "em aberto",
        "empty": "Ainda não há respostas. Rode: narrative-trace quiz",
    },
    "en": {
        "conf": "How sure are you? 1 = guess, 2 = maybe, 3 = sure: ",
        "ans": "Write your answer (Enter to skip): ", "right": "Right answer: ",
        "ok": "Did you get it? (y/n): ", "none": "No open questions.", "done": "Logged in ",
        "head": "Practice panel", "total": "Answers: {n}. Correct: {p}%.",
        "bycf": "By confidence (read it so: at confidence 3 the hit rate should be high):",
        "cf": "  confidence {c}: {n} answers, {p}% correct",
        "sure": "Sure (3) and wrong (this is where the misconception hides):", "nosure": "No wrong answers at confidence 3.",
        "kinds": "By topic (learned = 2 correct in a row):", "learned": "learned", "open": "open",
        "empty": "No answers yet. Run: narrative-trace quiz",
    },
}


def _lang():
    return "en" if (os.environ.get("NT_LANG") or "pt").lower().startswith("en") else "pt"


def _book(d):
    return os.path.join(os.path.dirname(os.path.abspath(d)), "scores.jsonl")


def latest_session(base):
    best = None
    for n in os.listdir(base) if os.path.isdir(base) else []:
        q = os.path.join(base, n, "quiz.jsonl")
        if os.path.exists(q) and (best is None or os.path.getmtime(q) > best[0]):
            best = (os.path.getmtime(q), os.path.join(base, n))
    return best[1] if best else None


def practice(d, ask=input, say=print):
    lg = _lang()
    t = T[lg]
    sid = os.path.basename(os.path.normpath(d))
    done = {(r.get("turn"), r.get("q")) for r in store.read_jsonl(_book(d)) if r.get("session") == sid}
    todo = [(r["turn"], it) for r in store.read_jsonl(os.path.join(d, "quiz.jsonl"))
            for it in r["items"] if (r["turn"], it["q"]) not in done]
    if not todo:
        say(t["none"])
        return 0
    n = 0
    try:
        for turn, it in todo:
            say("\n" + it["q"])
            c = ""
            while c not in ("1", "2", "3"):
                c = ask(t["conf"]).strip()
            mine = ask(t["ans"]).strip()
            say(t["right"] + it["a"])
            ok = ask(t["ok"]).strip().lower()[:1] in ("s", "y")
            row = {"ts": now_iso(), "session": sid, "turn": turn, "kind": it.get("kind") or "other",
                   "q": it["q"], "confidence": int(c), "answer": mine, "correct": ok}
            with open(_book(d), "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    except EOFError:
        pass
    say(t["done"] + _book(d))
    return n


def report(d, say=print):
    t = T[_lang()]
    rows = store.read_jsonl(_book(d))
    if not rows:
        say(t["empty"])
        return
    say(t["head"])
    say(t["total"].format(n=len(rows), p=round(100 * sum(r["correct"] for r in rows) / len(rows))))
    say(t["bycf"])
    for c in (1, 2, 3):
        part = [r for r in rows if r["confidence"] == c]
        if part:
            say(t["cf"].format(c=c, n=len(part), p=round(100 * sum(r["correct"] for r in part) / len(part))))
    wrong = [r for r in rows if r["confidence"] == 3 and not r["correct"]]
    say(t["sure"] if wrong else t["nosure"])
    for r in wrong[-5:]:
        say("  - " + r["q"])
    say(t["kinds"])
    for kind in sorted({r["kind"] for r in rows}):
        last = [r["correct"] for r in rows if r["kind"] == kind][-2:]
        state = t["learned"] if len(last) == 2 and all(last) else t["open"]
        say("  %s: %s" % (kind, state))
