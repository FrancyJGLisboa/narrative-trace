import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

HARNESSES = ("claude_code", "codex", "gemini_cli", "cursor")
WHY = ("The onClick calls handleCheckoutOld, which no longer exists. "
       "I will point it to handleCheckout.")
FINAL = "Fixed: the button now calls handleCheckout and all tests pass."
FULL = ("claude_code", "cursor")  # harnesses that expose the agent's mid-turn reason

# Ground truth (spec section 9.2): (kind, tool contains, target, status)
SHELL = "<shell>"
EVENTS_FULL = [
    ("turn_start", None, None, None),
    ("tool_result", "<investigate>", "src/Checkout.tsx", "ok"),
    ("tool_result", "<investigate>", "handleCheckout", "ok"),
    ("agent_text", None, None, None),
    ("tool_result", "<change>", "src/Checkout.tsx", "ok"),
    ("tool_result", SHELL, "npm test", "error"),
    ("tool_result", "<change>", "src/Checkout.tsx", "ok"),
    ("tool_result", SHELL, "npm test", "ok"),
    ("agent_text", None, None, None),
    ("turn_end", None, None, None),
]


def expected_events(harness):
    return EVENTS_FULL if harness in FULL else EVENTS_FULL[:3] + EVENTS_FULL[4:]


def expected_scenes(harness):
    if harness in FULL:
        return [("mission", [1], []), ("investigate", [2, 3], []), ("change", [4, 5], [WHY]),
                ("setback", [6], []), ("change", [7], []), ("verify", [8], []),
                ("closing", [9, 10], [])]
    return [("mission", [1], []), ("investigate", [2, 3], []), ("change", [4], []),
            ("setback", [5], []), ("change", [6], []), ("verify", [7], []),
            ("closing", [8, 9], [])]


def tmpdir(test):
    d = tempfile.mkdtemp(prefix="nt_")
    test.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
    return d
