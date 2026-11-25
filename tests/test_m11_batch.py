import json
import unittest

from narrative_trace import narrator, store
from tests.helpers import *  # noqa: F401,F403
from tests.test_m10_lessons import bash, ev, tempfile_dir


def make_dir():
    d = tempfile_dir()
    for e in [ev("turn_start", 1, text="go"), bash(2, "python3 a.py"), bash(3, "pytest -q"),
              bash(4, "ls", "error"), ev("turn_end", 5)]:
        store.append_event(d, e)
    return d


class BatchTest(unittest.TestCase):
    def test_one_call_for_the_whole_turn(self):
        calls = []

        def call(system, user):
            calls.append(user)
            n = len(json.loads(user)["scenes"])
            ok = {"mission": "You asked me to go.", "run": "I ran python3 a.py.",
                  "verify": "I ran pytest -q.", "setback": "ls failed.", "closing": "I finished."}
            return json.dumps([ok[s["phase"]] for s in json.loads(user)["scenes"]])

        rows = narrator.narrate_turn(make_dir(), 1, call=call)
        self.assertEqual(len(calls), 1)
        self.assertEqual({r["source"] for r in rows}, {"llm"})

    def test_bad_scene_in_batch_is_asked_again_alone(self):
        calls = []

        def call(system, user):
            calls.append(user)
            data = json.loads(user)
            if "scenes" in data:   # batch answer: one scene mentions a file that is not in the events
                return json.dumps(["You asked me to go.", "I ran python3 a.py.", "I ran pytest -q.",
                                   "I read secret.py.", "I finished."])
            return "ls failed."

        rows = narrator.narrate_turn(make_dir(), 1, call=call)
        self.assertEqual(len(calls), 2)
        self.assertEqual(rows[3]["text"], "ls failed.")

    def test_garbage_answer_falls_back_to_template(self):
        rows = narrator.narrate_turn(make_dir(), 1, call=lambda s, u: "not json at all")
        # scenes that name files or commands cannot pass without naming them
        self.assertEqual({r["source"] for r in rows if r["phase"] in ("run", "verify", "setback")},
                         {"template_fallback"})


if __name__ == "__main__":
    unittest.main()
