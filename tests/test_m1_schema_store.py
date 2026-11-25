import threading
import unittest

from helpers import tmpdir
from narrative_trace import store
from narrative_trace.schema import classify_phase, make_event, pick, redact, truncate


class M1(unittest.TestCase):
    def test_pick(self):
        d = {"a": "", "b": None, "c": "x", "n": {"k": "deep"}}
        self.assertEqual(pick(d, "a", "b", "c"), "x")
        self.assertEqual(pick(d, "n.k"), "deep")
        self.assertIsNone(pick(d, "zz"))
        self.assertEqual(pick("not a dict", "a", default=1), 1)

    def test_redact_truncate(self):
        s = redact("key sk-abcdefghijklmnopqrstuvwx and password=hunter2")
        self.assertNotIn("sk-abcdef", s)
        self.assertNotIn("hunter2", s)
        self.assertEqual(truncate("abcdefghij", 6), "abc...")
        self.assertIsNone(truncate(None, 5))

    def test_phase(self):
        cases = {("Read", "a.py"): "investigate", ("Grep", "x"): "investigate",
                 ("Edit", "a.py"): "change", ("Write", "a.py"): "change",
                 ("Bash", "npm test"): "verify", ("Bash", "ls -la"): "investigate", ("Bash", "make deploy"): "run",
                 ("Bash", "cat a.py"): "investigate",
                 ("Mystery", "x"): "other", ("apply_patch", ""): "change"}
        for (tool, target), phase in cases.items():
            self.assertEqual(classify_phase({"tool": tool, "target": target}), phase, tool)

    def test_concurrent_seq(self):
        d = tmpdir(self)

        def work(i):
            for j in range(5):
                kind = "turn_start" if (i == 0 and j == 0) else "tool_result"
                store.append_event(d, make_event(kind, "t", "s", tool="Read", target="f"))

        ts = [threading.Thread(target=work, args=(i,)) for i in range(10)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        seqs = [e["seq"] for e in store.read_events(d)]
        self.assertEqual(sorted(seqs), list(range(1, 51)))
        self.assertEqual(store.load_state(d)["current_turn"], 1)


if __name__ == "__main__":
    unittest.main()
