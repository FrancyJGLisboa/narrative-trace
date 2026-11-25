"""Command line: hook | narrate | install | uninstall | demo | where."""
import argparse
import json
import os
import subprocess
import sys
import traceback

from . import __version__, store

NOTES = {
    "codex": "Codex asks you to trust new hooks: open Codex and run /hooks once.",
    "gemini_cli": "Gemini CLI asks you to trust new project hooks the first time they run.",
    "cursor": "Restart Cursor so it reloads hooks.json.",
    "claude_code": "Start a new Claude Code session (or run /hooks) to load the hooks.",
}


def _spawn_narrator(d, turn):
    if os.environ.get("NT_SYNC") == "1":
        from .narrator import narrate_turn
        narrate_turn(d, turn)
        return
    launcher = os.path.join(os.path.dirname(os.path.abspath(__file__)), "launcher.py")
    args = [sys.executable, launcher, "narrate", "--session-dir", d, "--turn", str(turn)]
    kw = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
              close_fds=True)
    if os.name == "nt":
        kw["creationflags"] = 0x00000008 | 0x00000200
    else:
        kw["start_new_session"] = True
    subprocess.Popen(args, **kw)


def cmd_hook(a):
    d = None
    if os.environ.get("NT_NARRATING"):  # we are inside the narrator's own CLI call: stay silent
        return 0
    try:
        from .adapters import get_adapter
        raw = sys.stdin.read() if not sys.stdin.isatty() else ""
        try:
            payload = json.loads(raw) if raw.strip() else {}
        except ValueError:
            payload = {}
        if not isinstance(payload, (dict, list)):
            payload = {}
        meta = payload if isinstance(payload, dict) else {}
        adapter = get_adapter(a.harness)
        out = getattr(adapter, "STDOUT", {}).get(a.event)
        if out:
            sys.stdout.write(out + "\n")
            sys.stdout.flush()
        d = store.session_dir(meta)
        state = store.load_state(d)
        before = state.get("cc_transcript_offset")
        events = adapter.to_events(a.event, payload, store.session_id(meta), state)
        updates = {}
        if state.get("cc_transcript_offset") != before:
            updates["cc_transcript_offset"] = state["cc_transcript_offset"]
        if events or updates:
            stored = store.append_events(d, events, updates)
            ends = [e for e in stored if e["kind"] == "turn_end"]
            if ends:
                _spawn_narrator(d, ends[-1]["turn"])
    except BaseException:  # never break the agent
        if d:
            store.log_error(d, "[hook %s/%s]\n%s" % (a.harness, a.event, traceback.format_exc()))
    return 0


def cmd_narrate(a):
    from .narrator import narrate_all, narrate_turn
    if a.turn is not None:
        narrate_turn(a.session_dir, a.turn)
    else:
        narrate_all(a.session_dir)
    print(os.path.join(a.session_dir, "story.md"))
    return 0


def _targets(a):
    from .install import ALL, detect
    if a.harness == "all":
        return list(ALL)
    if a.harness == "auto":
        found = detect(a.project)
        if not found:
            print("No harness detected. Use --harness claude_code|codex|gemini_cli|cursor|all")
        return found
    return [a.harness]


def cmd_install(a):
    from .install import install
    for h in _targets(a):
        install(h, a.project, a.scope, a.dry_run)
        if not a.dry_run:
            print("  note: " + NOTES[h])
    if not a.dry_run:
        where = "<each project>/.narrative" if a.scope == "user" else \
            os.path.join(os.path.abspath(a.project), ".narrative")
        print("Stories will appear in %s/<session>/story.md (override with NT_HOME)" % where)
    return 0


def cmd_uninstall(a):
    from .install import uninstall
    for h in _targets(a):
        uninstall(h, a.project, a.scope)
    return 0


def cmd_quiz(a):
    from . import scorebook
    d = a.session_dir or scorebook.latest_session(
        os.environ.get("NT_HOME") or os.path.join(os.getcwd(), ".narrative"))
    if not d:
        print("No quiz found. Finish a turn first, or pass --session-dir.")
        return 1
    scorebook.report(d) if a.report else scorebook.practice(d)
    return 0


def cmd_demo(a):
    from .demo import run_demo
    print(run_demo(a.harness, a.out))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="narrative-trace",
                                description="First-person scene narration for AI agent harnesses.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd")
    h = sub.add_parser("hook", help="called by the harness; reads the payload on stdin")
    h.add_argument("--harness", required=True)
    h.add_argument("--event", required=True)
    n = sub.add_parser("narrate", help="write scenes and story.md for a session")
    n.add_argument("--session-dir", required=True)
    n.add_argument("--turn", type=int)
    n.add_argument("--all", action="store_true")
    for name in ("install", "uninstall"):
        i = sub.add_parser(name, help=name + " hooks in a harness config")
        i.add_argument("--harness", default="auto",
                       help="claude_code | codex | gemini_cli | cursor | all | auto (default)")
        i.add_argument("--project", default=".")
        i.add_argument("--scope", choices=("project", "user"), default="project")
        if name == "install":
            i.add_argument("--dry-run", action="store_true")
    qz = sub.add_parser("quiz", help="answer the self-check questions, log confidence, see weak spots")
    qz.add_argument("--session-dir")
    qz.add_argument("--report", action="store_true")
    dm = sub.add_parser("demo", help="replay a bundled example session and narrate it")
    dm.add_argument("--harness", default="claude_code")
    dm.add_argument("--out", default="narrative-demo")
    a = p.parse_args(argv)
    if not a.cmd:
        p.print_help()
        return 0
    fn = {"hook": cmd_hook, "narrate": cmd_narrate, "install": cmd_install,
          "uninstall": cmd_uninstall, "demo": cmd_demo, "quiz": cmd_quiz}[a.cmd]
    rc = fn(a)
    if a.cmd == "hook":
        sys.exit(0)
    return rc
