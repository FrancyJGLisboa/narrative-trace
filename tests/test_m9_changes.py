import unittest

from narrative_trace import narrator, schema
from narrative_trace.adapters import claude_code
from narrative_trace.chunker import build_scenes
from tests.helpers import *  # noqa: F401,F403


def run(payloads):
    ev, state = [], {}
    for name, pl in payloads:
        ev += claude_code.to_events(name, pl, "s", state)
    for i, e in enumerate(ev, 1):
        e["seq"], e["turn"] = i, 1
    return build_scenes(ev)


class ChangeTest(unittest.TestCase):
    def edit(self, **inp):
        return ("PostToolUse", {"tool_name": "Edit", "tool_input": dict(file_path="src/calc.py", **inp),
                                "tool_response": {"success": True}})

    def test_edit_records_before_and_after(self):
        sc = run([self.edit(old_string="return a-b", new_string="return a+b")])
        self.assertEqual(sc[0]["changes"][0]["before"], "return a-b")
        txt = narrator.template_scene(sc[0], "en")
        self.assertIn('replaced "return a-b" with "return a+b"', txt)

    def test_write_records_new_file(self):
        pl = ("PostToolUse", {"tool_name": "Write", "tool_input": {"file_path": "a.py", "content": "x = 1\n"},
                              "tool_response": {}})
        sc = run([pl])
        self.assertIn('I wrote: "x = 1"', narrator.template_scene(sc[0], "en"))

    def test_secrets_in_changes_are_redacted(self):
        c = schema.extract_change({"file_path": "a", "old_string": "k", "new_string": "key=sk-ABCDEFGHIJKLMNOPQRSTUV1234"})
        ev = schema.make_event("tool_result", "claude_code", "s", tool="Edit", target="a", status="ok", change=c)
        self.assertNotIn("ABCDEFGHIJKLMNOPQRSTUV1234", ev["change"]["after"])

    def test_failed_edit_has_no_change_and_long_snippets_are_cut(self):
        ev = schema.make_event("tool_result", "claude_code", "s", change={"before": None, "after": "y" * 999})
        self.assertLessEqual(len(ev["change"]["after"]), 160)

    def test_llm_scene_may_quote_the_snippet(self):
        sc = run([self.edit(old_string="return a-b", new_string="return a+b")])[0]
        good = "I changed calc.py: it said return a-b and now says return a+b."
        text, src = narrator.llm_scene(sc, "", "en", lambda s, u: good)
        self.assertEqual(src, "llm")


if __name__ == "__main__":
    unittest.main()
