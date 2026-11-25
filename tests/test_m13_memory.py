import os
import tempfile
import unittest

from narrative_trace import memory, narrator, store
from tests.helpers import *  # noqa: F401,F403
from tests.test_m10_lessons import bash, ev


def session(parent, name, day, cmds):
    d = os.path.join(parent, name)
    os.makedirs(d)
    ts = "2026-01-%02dT10:00:00.000Z" % day
    evs = [ev("turn_start", 1, text="go", ts=ts)] + [bash(i + 2, c) for i, c in enumerate(cmds)]
    evs.append(ev("turn_end", len(evs) + 1))
    for e in evs:
        e["ts"] = ts
        store.append_event(d, e)
    return d


def keys(rows):
    return [k for r in rows for k in r["lesson_keys"]]


class MemoryTest(unittest.TestCase):
    def setUp(self):
        self.parent = tempfile.mkdtemp()

    def test_a_concept_taught_in_an_earlier_session_is_not_repeated(self):
        a = session(self.parent, "A", 1, ["python3 x.py"])
        b = session(self.parent, "B", 2, ["python3 y.py", "pytest -q"])
        self.assertIn("command", keys(narrator.narrate_turn(a, 1)))
        kb = keys(narrator.narrate_turn(b, 1))
        self.assertNotIn("command", kb)
        self.assertIn("test", kb)
        self.assertEqual(set(memory.load(a)), {"command", "test"})

    def test_rebuilding_an_old_session_gives_the_same_story(self):
        a = session(self.parent, "A", 1, ["python3 x.py"])
        b = session(self.parent, "B", 2, ["python3 y.py"])
        first = keys(narrator.narrate_turn(a, 1))
        narrator.narrate_turn(b, 1)
        os.remove(os.path.join(a, "scenes.jsonl"))
        self.assertEqual(keys(narrator.narrate_turn(a, 1)), first)

    def test_corrupt_memory_file_is_ignored(self):
        a = session(self.parent, "A", 1, ["python3 x.py"])
        with open(os.path.join(self.parent, "concepts.json"), "w") as f:
            f.write("{not json")
        self.assertIn("command", keys(narrator.narrate_turn(a, 1)))


if __name__ == "__main__":
    unittest.main()
