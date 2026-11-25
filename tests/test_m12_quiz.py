import os
import unittest

from narrative_trace import narrator, store
from tests.helpers import *  # noqa: F401,F403
from tests.test_m10_lessons import bash, ev, tempfile_dir


def edit_ev(seq):
    return ev("tool_result", seq, tool="Edit", target="/p/calc.py", status="ok", summary="Edit /p/calc.py",
              change={"before": "return a-b", "after": "return a+b"})


def story(d):
    with open(os.path.join(d, "story.md"), encoding="utf-8") as f:
        return f.read()


class QuizTest(unittest.TestCase):
    def build(self, events):
        d = tempfile_dir()
        for e in events:
            store.append_event(d, e)
        narrator.narrate_turn(d, 1)
        return d

    def test_questions_come_from_the_events_with_answers_hidden(self):
        d = self.build([ev("turn_start", 1, text="go"), edit_ev(2), bash(3, "pytest -q"), ev("turn_end", 4)])
        s = story(d)
        self.assertIn("**Confira se entendeu**", s)
        self.assertIn("O que foi trocado em calc.py?", s)
        self.assertIn('<details><summary>Resposta</summary>Saiu "return a-b" e entrou "return a+b".</details>', s)
        self.assertIn("A verificação passou no fim?", s)
        self.assertLessEqual(s.count("<details>"), 3)

    def test_failed_check_is_reported_as_failed(self):
        d = self.build([ev("turn_start", 1, text="go"), bash(2, "pytest -q", "error"), ev("turn_end", 3)])
        s = story(d)   # a failing command becomes a setback scene
        self.assertIn("O que falhou?", s)
        self.assertIn("Bash pytest -q</details>", s)

    def test_no_quiz_while_the_turn_is_running(self):
        d = self.build([ev("turn_start", 1, text="go"), edit_ev(2)])
        self.assertNotIn("Confira", story(d))

    def test_off_switch(self):
        os.environ["NT_LESSONS"] = "off"
        try:
            d = self.build([ev("turn_start", 1, text="go"), edit_ev(2), ev("turn_end", 3)])
        finally:
            del os.environ["NT_LESSONS"]
        self.assertNotIn("Confira", story(d))


if __name__ == "__main__":
    unittest.main()
