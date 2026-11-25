import os
import unittest

from narrative_trace import lessons, narrator, store
from narrative_trace.chunker import build_scenes
from tests.helpers import *  # noqa: F401,F403
from tests.test_m9_changes import run


def ev(kind, seq, turn=1, **kw):
    e = {"v": 1, "seq": seq, "turn": turn, "kind": kind, "tool": None, "target": None,
         "status": None, "summary": None, "text": None, "change": None, "ts": "t",
         "session": "s", "harness": "claude_code"}
    e.update(kw)
    return e


def bash(seq, cmd, status="ok", turn=1):
    return ev("tool_result", seq, turn, tool="Bash", target=cmd, status=status, summary="Bash " + cmd)


class LessonTest(unittest.TestCase):
    def scenes(self, cmds):
        events = [ev("turn_start", 1, text="go")] + [bash(i + 2, c) for i, c in enumerate(cmds)]
        return build_scenes(events)

    def test_test_command_gets_the_test_lesson_once(self):
        s = self.scenes(["pytest -q"])[1]
        text, keys = lessons.lesson_for(s, set(), "en")
        self.assertTrue(text.startswith("To understand: A test is"))
        again, _ = lessons.lesson_for(s, set(keys), "en")
        self.assertNotIn("A test is", again)   # not repeated: the next concept comes instead

    def test_each_concept_once_per_session(self):
        d = tempfile_dir()
        events = [ev("turn_start", 1, text="go"), bash(2, "pytest -q"), bash(3, "ls", "error"),
                  ev("turn_end", 4)]
        for e in events:
            store.append_event(d, e)
        rows = narrator.narrate_turn(d, 1)
        keys = [k for r in rows for k in r["lesson_keys"]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertIn("test", keys)
        with open(os.path.join(d, "story.md"), encoding="utf-8") as f:
            story = f.read()
        self.assertIn("> Para entender:", story)

    def test_can_be_turned_off(self):
        os.environ["NT_LESSONS"] = "off"
        try:
            self.assertEqual(lessons.lesson_for(self.scenes(["pytest"])[1], set()), (None, []))
        finally:
            del os.environ["NT_LESSONS"]

    def test_edit_and_new_file(self):
        sc = run([("PostToolUse", {"tool_name": "Write", "tool_input": {"file_path": "a.py", "content": "x"},
                                   "tool_response": {}})])[0]
        self.assertEqual(lessons.detect(sc), ["new_file"])


def tempfile_dir():
    import tempfile
    return tempfile.mkdtemp()


if __name__ == "__main__":
    unittest.main()
