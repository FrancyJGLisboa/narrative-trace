import unittest

from helpers import HARNESSES, SHELL, expected_events, tmpdir
from narrative_trace import store
from narrative_trace.adapters import get_adapter
from narrative_trace.demo import iter_payloads
from narrative_trace.schema import classify_phase, is_shell


def replay_direct(harness, workdir):
    adapter = get_adapter(harness)
    d = None
    for event, payload in iter_payloads(harness, workdir):
        d = store.session_dir(dict(payload, cwd=workdir))
        state = store.load_state(d)
        evs = adapter.to_events(event, payload, store.session_id(payload), state)
        store.append_events(d, evs, {"cc_transcript_offset": state["cc_transcript_offset"]})
    return store.read_events(d)


def check(test, harness, events):
    exp = expected_events(harness)
    test.assertEqual([e["kind"] for e in events], [x[0] for x in exp], harness)
    for e, (kind, tool, target, status) in zip(events, exp):
        if tool == SHELL:
            test.assertTrue(is_shell(e["tool"]), (harness, e))
        elif tool in ("<change>", "<investigate>"):
            test.assertEqual(classify_phase(e), tool.strip("<>"), (harness, e))
        if target:
            test.assertIn(target, e["target"], harness)
        if status:
            test.assertEqual(e["status"], status, (harness, e))
    test.assertEqual([e["seq"] for e in events], list(range(1, len(exp) + 1)))


class M2(unittest.TestCase):
    def test_all_harnesses(self):
        for h in HARNESSES:
            with self.subTest(h=h):
                check(self, h, replay_direct(h, tmpdir(self)))

    def test_unknown_and_empty(self):
        for h in HARNESSES:
            a = get_adapter(h)
            self.assertEqual(a.to_events("NoSuchEvent", {}, "s", {}), [])
            for ev in a.EVENTS:
                a.to_events(ev, {}, "s", {})  # must not raise

    def test_generic(self):
        a = get_adapter("generic")
        evs = a.to_events("", {"events": [{"kind": "turn_start", "text": "hi"},
                                          {"kind": "bogus"}]}, "s", {})
        self.assertEqual([e["kind"] for e in evs], ["turn_start"])


if __name__ == "__main__":
    unittest.main()


class FailureFormats(unittest.TestCase):
    """Documented error shapes from each harness end up as status=error with a useful summary."""

    def one(self, harness, event, payload):
        evs = get_adapter(harness).to_events(event, payload, "s", {})
        return [e for e in evs if e["kind"] == "tool_result"][0]

    def test_claude_post_tool_use_failure(self):
        e = self.one("claude_code", "PostToolUseFailure", {
            "tool_name": "Bash", "tool_input": {"command": "npm test"},
            "error": "Exit code 1\nError: Cannot find module 'express'"})
        self.assertEqual(e["status"], "error")
        self.assertEqual(e["summary"], "Bash npm test: Error: Cannot find module 'express' (exit 1)")

    def test_codex_text_exit_code(self):
        e = self.one("codex", "PostToolUse", {"tool_name": "Bash", "tool_input": {"command": "pytest"},
                                              "tool_response": "Exit code: 2\nOutput:\nE   boom"})
        self.assertEqual(e["status"], "error")
        ok = self.one("codex", "PostToolUse", {"tool_name": "Bash", "tool_input": {"command": "ls"},
                                               "tool_response": "Exit code: 0\nOutput:\na"})
        self.assertEqual(ok["status"], "ok")

    def test_cursor_stringified_output(self):
        e = self.one("cursor", "postToolUse", {"tool_name": "run_terminal_cmd",
                                               "tool_input": {"command": "npm test"},
                                               "tool_output": '{"exitCode": 1, "output": "x failed"}'})
        self.assertEqual(e["status"], "error")

    def test_gemini_error_field(self):
        e = self.one("gemini_cli", "AfterTool", {"tool_name": "write_file",
                                                 "tool_input": {"file_path": "a.py"},
                                                 "tool_response": {"llmContent": "", "error": "denied"}})
        self.assertEqual(e["status"], "error")

    def test_non_shell_text_mentioning_exit_code_is_ok(self):
        e = self.one("codex", "PostToolUse", {"tool_name": "Read", "tool_input": {"file_path": "a.md"},
                                              "tool_response": "docs: exit code 1 means failure"})
        self.assertEqual(e["status"], "ok")
