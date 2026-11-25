"""The "To understand" layer: short, fixed explanations of concepts, one time each per session.

The texts are written by hand and never produced by a model, so they cannot invent facts
about the session. They explain the idea, not the agent's motive. NT_LESSONS=off turns them off.
"""
import os
import re

LABEL = {"pt": "Para entender", "en": "To understand"}

GLOSSARY = {
    "read": (
        "Ler um arquivo não muda nada. É só olhar o código, como ler um documento antes de editar.",
        "Reading a file changes nothing. It is only looking at the code, like reading a document before you edit it."),
    "search": (
        "Buscar é procurar um texto ou um arquivo no projeto, como usar Ctrl+F em todas as pastas.",
        "Searching means looking for a text or a file in the project, like Ctrl+F across every folder."),
    "edit": (
        "Editar muda o código de verdade. O trecho antigo sai e o novo entra, como corrigir uma frase num documento.",
        "Editing really changes the code. The old piece goes out and the new piece comes in, like fixing a sentence in a document."),
    "new_file": (
        "Criar um arquivo novo adiciona uma peça nova ao projeto. Um projeto é um conjunto de arquivos.",
        "Creating a new file adds a new piece to the project. A project is a set of files."),
    "command": (
        "Um comando é uma instrução escrita no terminal. O computador a executa e mostra o resultado como texto.",
        "A command is an instruction typed in the terminal. The computer runs it and shows the result as text."),
    "test": (
        "Um teste é um programa pequeno que confere se outro programa faz o que deveria. Se passa, o resultado esperado apareceu.",
        "A test is a small program that checks that another program does what it should. If it passes, the expected result appeared."),
    "install": (
        "Instalar baixa pacotes: código escrito por outras pessoas que o projeto passa a usar.",
        "Installing downloads packages: code written by other people that the project then uses."),
    "git": (
        "Git guarda o histórico do projeto. Cada commit é um ponto salvo para o qual dá para voltar.",
        "Git keeps the history of the project. Each commit is a saved point you can go back to."),
    "failure": (
        "Uma falha mostra onde está o problema. A mensagem de erro é a pista. O número de saída 0 quer dizer sucesso, e qualquer outro número quer dizer falha.",
        "A failure shows where the problem is. The error message is the clue. Exit number 0 means success, and any other number means failure."),
}

_TEST = re.compile(r"(?i)\b(pytest|unittest|jest|vitest|mocha|rspec|go test|cargo test|npm (run )?test|yarn test|make test)\b")
_INSTALL = re.compile(r"(?i)\b(npm|pnpm|yarn|pip3?|pipx|brew|apt(-get)?|cargo|gem) (install|add|i)\b")
_GIT = re.compile(r"(?i)\bgit\s+\w+")
_SEARCH = re.compile(r"(?i)(^|\s)(grep|rg|find|ls|glob)\b|^(grep|glob|search)")


def detect(scene):
    """Return concept keys of one scene, most useful first."""
    text = " ".join(scene.get("facts") or []) + " " + " ".join(scene.get("targets") or [])
    phase = scene.get("phase")
    keys = []
    if scene.get("status") == "error":
        keys.append("failure")
    if _TEST.search(text):
        keys.append("test")
    if _INSTALL.search(text):
        keys.append("install")
    if _GIT.search(text):
        keys.append("git")
    if phase == "change":
        news = [c for c in scene.get("changes") or [] if not c.get("before")]
        keys.append("new_file" if news and len(news) == len(scene["changes"]) else "edit")
    elif phase == "investigate":
        keys.append("search" if _SEARCH.search(text) or any(
            (f.split() or [""])[0].lower() in ("grep", "glob") for f in scene.get("facts") or []) else "read")
    elif phase in ("run", "verify"):
        keys.append("command")
    return list(dict.fromkeys(keys))


def lesson_for(scene, seen, lg="pt"):
    """Return (text, keys): the first unseen concept of the scene, or (None, [])."""
    if (os.environ.get("NT_LESSONS") or "").lower() in ("off", "0", "no"):
        return None, []
    for k in detect(scene):
        if k not in seen:
            return "%s: %s" % (LABEL[lg], GLOSSARY[k][1 if lg == "en" else 0]), [k]
    return None, []
