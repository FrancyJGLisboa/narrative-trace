import os
import unittest

from narrative_trace import narrator, scorebook, store
from tests.helpers import *  # noqa: F401,F403
from tests.test_m10_lessons import bash, ev, tempfile_dir
from tests.test_m12_quiz import edit_ev


def quiz_dir():
    parent = tempfile_dir()
    d = os.path.join(parent, "S1")
    os.makedirs(d)
    for e in [ev("turn_start", 1, text="go"), edit_ev(2), bash(3, "pytest -q"), ev("turn_end", 4)]:
        store.append_event(d, e)
    narrator.narrate_turn(d, 1)
    return d


def feed(answers):
    it = iter(answers)
    def ask(prompt):
        try:
            return next(it)
        except StopIteration:
            raise EOFError   # like input() at the end of a pipe
    return ask


class ScorebookTest(unittest.TestCase):
    def test_practice_logs_confidence_answer_and_result(self):
        d = quiz_dir()
        n = scorebook.practice(d, ask=feed(["3", "foi a soma", "n", "2", "", "s", "1", "", "s"]), say=lambda *a: None)
        self.assertEqual(n, 3)
        rows = store.read_jsonl(scorebook._book(d))
        self.assertEqual([(r["confidence"], r["correct"]) for r in rows], [(3, False), (2, True), (1, True)])
        self.assertEqual(rows[0]["answer"], "foi a soma")
        self.assertEqual(rows[0]["kind"], "swap")

    def test_answered_questions_are_not_asked_twice(self):
        d = quiz_dir()
        scorebook.practice(d, ask=feed(["3", "", "s"] * 3), say=lambda *a: None)
        lines = []
        scorebook.practice(d, ask=feed([]), say=lines.append)
        self.assertIn("Nenhuma pergunta aberta.", lines)

    def test_report_shows_sure_and_wrong(self):
        d = quiz_dir()
        scorebook.practice(d, ask=feed(["3", "", "n", "1", "", "n", "2", "", "s"]), say=lambda *a: None)
        out = []
        scorebook.report(d, say=out.append)
        text = "\n".join(out)
        self.assertIn("Certeza 3 e errou", text)
        self.assertIn("O que foi trocado em calc.py?", text)
        self.assertIn("certeza 3: 1 respostas, 0% de acertos", text)

    def test_learned_needs_two_correct_in_a_row(self):
        d = quiz_dir()
        book = scorebook._book(d)
        base = {"ts": "t", "session": "S1", "turn": 1, "q": "q", "confidence": 3, "answer": ""}
        with open(book, "w") as f:
            import json
            for ok in (False, True, True):
                f.write(json.dumps(dict(base, kind="swap", correct=ok)) + "\n")
            for ok in (True, False):
                f.write(json.dumps(dict(base, kind="verify", correct=ok)) + "\n")
        out = []
        scorebook.report(d, say=out.append)
        text = "\n".join(out)
        self.assertIn("swap: aprendido", text)
        self.assertIn("verify: em aberto", text)

    def test_end_of_input_stops_cleanly(self):
        d = quiz_dir()
        self.assertEqual(scorebook.practice(d, ask=feed(["3"]), say=lambda *a: None), 0)


if __name__ == "__main__":
    unittest.main()
