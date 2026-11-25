import unittest

from helpers import FINAL, HARNESSES, expected_scenes, tmpdir
from narrative_trace.chunker import build_scenes
from test_m2_adapters import replay_direct


class M4(unittest.TestCase):
    def test_scenes(self):
        for h in HARNESSES:
            with self.subTest(h=h):
                scenes = build_scenes(replay_direct(h, tmpdir(self)))
                got = [(s["phase"], s["seqs"], s["reasons"]) for s in scenes]
                self.assertEqual(got, expected_scenes(h))
                self.assertEqual(scenes[-1]["final"], FINAL)
                self.assertEqual(scenes[0]["prompt"], "Fix the checkout button and run the tests")
                self.assertEqual(scenes[3]["status"], "error")

    def test_reason_splits_same_phase(self):
        evs = [{"seq": 1, "turn": 1, "kind": "tool_result", "tool": "Read", "target": "a.py",
                "status": "ok", "summary": "Read a.py"},
               {"seq": 2, "turn": 1, "kind": "agent_text", "text": "Now b."},
               {"seq": 3, "turn": 1, "kind": "tool_result", "tool": "Read", "target": "b.py",
                "status": "ok", "summary": "Read b.py"}]
        s = build_scenes(evs)
        self.assertEqual([x["seqs"] for x in s], [[1], [2, 3]])
        self.assertEqual(s[1]["reasons"], ["Now b."])

    def test_max_events_per_scene(self):
        evs = [{"seq": i, "turn": 1, "kind": "tool_result", "tool": "Read", "target": "f%d" % i,
                "status": "ok", "summary": "r"} for i in range(1, 11)]
        self.assertEqual([len(x["seqs"]) for x in build_scenes(evs)], [8, 2])


if __name__ == "__main__":
    unittest.main()
