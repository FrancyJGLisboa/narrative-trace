"""Narrator through the harness's own CLI, so a subscription is enough: no API key.

NT_LLM=auto|claude|codex|copilot|gemini   pick a built-in command ("auto" = the session's harness)
NT_LLM_CMD="my-tool --flag"               any command: prompt on stdin, scene text on stdout
"""
import os
import shlex
import shutil
import subprocess
import tempfile

GUARD = "NT_NARRATING"  # set for the child; hooks exit at once when it is set (no loop)
TIMEOUT = 120
HARNESS_CLI = {"claude_code": "claude", "codex": "codex", "gemini_cli": "gemini"}
ORDER = ("claude", "codex", "copilot", "gemini")


def enabled():
    return bool(os.environ.get("NT_LLM") or os.environ.get("NT_LLM_CMD"))


def _argv(name, system, tmp):
    """Return (argv, prompt_prefix, output_file). Only the claude and codex commands are verified."""
    if name == "claude":
        return ["claude", "-p", "--system-prompt", system, "--tools", "",
                "--no-session-persistence", "--setting-sources", "project"], "", None
    if name == "codex":
        out = os.path.join(tmp, "last.txt")
        return ["codex", "exec", "--skip-git-repo-check", "--ephemeral", "--ignore-user-config",
                "--ignore-rules", "-s", "read-only",
                "-o", out, "-"], system + "\n\n", out
    if name == "copilot":
        return ["copilot", "-p", ""], system + "\n\n", None
    if name == "gemini":
        return ["gemini", "-p", ""], system + "\n\n", None
    raise ValueError("unknown NT_LLM value: %s" % name)


def pick(harness=None):
    want = (os.environ.get("NT_LLM") or "").lower()
    if want in ("", "auto", "1", "true"):
        first = HARNESS_CLI.get(harness or "")
        for n in ([first] if first else []) + list(ORDER):
            if n and shutil.which(n):
                return n
        raise RuntimeError("no supported CLI found on PATH")
    return want


def make_call(harness=None):
    """Return call(system, user) -> text, backed by a subscription CLI."""
    def call(system, user):
        env = dict(os.environ, **{GUARD: "1"})
        with tempfile.TemporaryDirectory() as tmp:   # neutral cwd: no project instructions
            custom = os.environ.get("NT_LLM_CMD")
            if custom:
                argv, out, stdin = shlex.split(custom), None, system + "\n\n" + user
            else:
                name = pick(harness)
                argv, prefix, out = _argv(name, system, tmp)
                stdin = prefix + user
                if name in ("copilot", "gemini"):
                    argv, stdin = argv[:-1] + [stdin], None   # these two take the prompt as an argument
            r = subprocess.run(argv, input=stdin, capture_output=True, text=True,
                               cwd=tmp, env=env, timeout=TIMEOUT)
            if out and os.path.exists(out):
                with open(out, encoding="utf-8") as f:
                    return f.read()
            if r.returncode != 0:
                raise RuntimeError("narrator CLI failed: %s" % r.stderr[-300:])
            return r.stdout
    return call
