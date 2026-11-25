"""Self-check questions at the end of a turn. Built from the events, never by a model.

The answer sits in a collapsed block, so the reader can try first. NT_LESSONS=off hides them.
"""
import os

from .lessons import GLOSSARY

TITLE = {"pt": "Confira se entendeu", "en": "Check that you understood"}
ANSWER = {"pt": "Resposta", "en": "Answer"}
CONCEPT_Q = {
    "read": ("Ler um arquivo muda o código?", "Does reading a file change the code?"),
    "search": ("O que significa buscar no projeto?", "What does searching the project mean?"),
    "edit": ("O que acontece quando o agente edita um arquivo?", "What happens when the agent edits a file?"),
    "new_file": ("O que significa criar um arquivo novo?", "What does creating a new file mean?"),
    "command": ("O que é um comando?", "What is a command?"),
    "test": ("Para que serve um teste?", "What is a test for?"),
    "install": ("O que faz instalar um pacote?", "What does installing a package do?"),
    "git": ("Para que serve um commit?", "What is a commit for?"),
    "failure": ("O que quer dizer um erro com número de saída diferente de 0?",
                "What does an error with an exit number other than 0 mean?"),
}
T = {
    "pt": {
        "swap_q": "O que foi trocado em {file}?", "swap_a": 'Saiu "{before}" e entrou "{after}".',
        "new_q": "Qual arquivo novo foi criado?", "new_a": '{file}, com: "{after}".',
        "verify_q": "A verificação passou no fim?", "pass": "Sim, passou.", "fail": "Não. {fact}",
        "setback_q": "O que falhou?",
    },
    "en": {
        "swap_q": "What was replaced in {file}?", "swap_a": 'Out went "{before}" and in came "{after}".',
        "new_q": "Which new file was created?", "new_a": '{file}, with: "{after}".',
        "verify_q": "Did the check pass at the end?", "pass": "Yes, it passed.", "fail": "No. {fact}",
        "setback_q": "What failed?",
    },
}
MAX_ITEMS = 3


def _name(path):
    return os.path.basename((path or "").rstrip("/")) or "-"


def build_quiz(scenes, rows, lg="pt"):
    """scenes: chunker scenes of one turn. rows: the narrated rows (carry lesson_keys)."""
    if (os.environ.get("NT_LESSONS") or "").lower() in ("off", "0", "no"):
        return []
    t, items = T[lg], []
    for s in scenes:
        c = next((c for c in s.get("changes") or [] if c.get("before")), None)
        if c:
            items.append((t["swap_q"].format(file=_name(c.get("target"))),
                          t["swap_a"].format(before=c["before"], after=c["after"]), "swap"))
            break
    else:
        for s in scenes:
            for c in s.get("changes") or []:
                items.append((t["new_q"], t["new_a"].format(file=_name(c.get("target")), after=c["after"]), "new_file"))
                break
            if items:
                break
    verify = [s for s in scenes if s["phase"] == "verify"]
    if verify:
        last = verify[-1]
        ans = t["fail"].format(fact=(last.get("facts") or ["?"])[0]) if last["status"] == "error" else t["pass"]
        items.append((t["verify_q"], ans, "verify"))
    else:
        bad = [s for s in scenes if s["phase"] == "setback"]
        if bad:
            items.append((t["setback_q"], (bad[0].get("facts") or ["?"])[0], "setback"))
    for r in rows:
        for k in r.get("lesson_keys") or []:
            items.append((CONCEPT_Q[k][1 if lg == "en" else 0], GLOSSARY[k][1 if lg == "en" else 0], "concept:" + k))
            return items[:MAX_ITEMS]
    return items[:MAX_ITEMS]


def render_block(items, lg="pt"):
    if not items:
        return []
    out = ["**%s**" % TITLE[lg], ""]
    for i, it in enumerate(items, 1):
        out += ["%d. %s" % (i, it["q"]), "   <details><summary>%s</summary>%s</details>" % (ANSWER[lg], it["a"])]
    return out + [""]
