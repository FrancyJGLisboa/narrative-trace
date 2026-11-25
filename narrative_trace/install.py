"""Write (or remove) Narrative Trace hook entries in each harness's config file."""
import json
import os
import shutil
import sys

from .adapters import get_adapter

MARK = "narrative_trace"
LAUNCHER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "launcher.py")

CONFIG = {  # harness: (project-relative path, user path)
    "claude_code": (".claude/settings.json", "~/.claude/settings.json"),
    "codex": (".codex/hooks.json", "~/.codex/hooks.json"),
    "gemini_cli": (".gemini/settings.json", "~/.gemini/settings.json"),
    "cursor": (".cursor/hooks.json", "~/.cursor/hooks.json"),
}
BINARIES = {"claude_code": ["claude"], "codex": ["codex"], "gemini_cli": ["gemini"],
            "cursor": ["cursor", "cursor-agent"]}
ALL = tuple(CONFIG)


def command(harness, event):
    return '"%s" "%s" hook --harness %s --event %s' % (sys.executable, LAUNCHER, harness, event)


def config_path(harness, project, scope):
    rel, user = CONFIG[harness]
    if scope == "user":
        return os.path.expanduser(user)
    return os.path.join(os.path.abspath(project), rel)


def detect(project):
    found = []
    for h in ALL:
        rel, user = CONFIG[h]
        top = rel.split("/")[0]
        if (os.path.isdir(os.path.join(project, top)) or os.path.isdir(os.path.expanduser("~/" + top))
                or any(shutil.which(b) for b in BINARIES[h])):
            found.append(h)
    return found


def _is_ours(entry):
    return MARK in json.dumps(entry)


def _strip(cfg, harness):
    hooks = cfg.get("hooks")
    if not isinstance(hooks, dict):
        return
    for ev in list(hooks):
        groups = hooks[ev]
        if not isinstance(groups, list):
            continue
        kept = [g for g in groups if not _is_ours(g)]
        if kept:
            hooks[ev] = kept
        else:
            del hooks[ev]


def _entry(harness, event):
    cmd = command(harness, event)
    if harness == "cursor":
        return {"command": cmd}
    hook = {"type": "command", "command": cmd}
    if harness == "gemini_cli":
        hook = {"name": "narrative-trace", "type": "command", "command": cmd}
    group = {"hooks": [hook]}
    if event in ("PostToolUse", "PostToolUseFailure", "AfterTool", "BeforeAgent"):
        group = {"matcher": "*", "hooks": [hook]}
    return group


def build(harness, existing):
    cfg = json.loads(json.dumps(existing)) if isinstance(existing, dict) else {}
    _strip(cfg, harness)
    if harness == "cursor":
        cfg.setdefault("version", 1)
    hooks = cfg.setdefault("hooks", {})
    for ev in get_adapter(harness).EVENTS:
        hooks.setdefault(ev, []).append(_entry(harness, ev))
    return cfg


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def _write(path, cfg):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")


def install(harness, project=".", scope="project", dry_run=False, out=sys.stdout):
    path = config_path(harness, project, scope)
    cfg = build(harness, _load(path))
    if dry_run:
        out.write("# would write %s\n%s\n" % (path, json.dumps(cfg, indent=2, ensure_ascii=False)))
    else:
        _write(path, cfg)
        out.write("installed %s hooks -> %s\n" % (harness, path))
    return path


def uninstall(harness, project=".", scope="project", out=sys.stdout):
    path = config_path(harness, project, scope)
    if not os.path.exists(path):
        return path
    cfg = _load(path)
    _strip(cfg, harness)
    _write(path, cfg)
    out.write("removed %s hooks from %s\n" % (harness, path))
    return path
