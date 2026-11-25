import json
import os
import subprocess
import sys
import time
import unittest

from helpers import HARNESSES, tmpdir
from narrative_trace import store
from narrative_trace.adapters import get_adapter
from narrative_trace.demo import LAUNCHER, iter_payloads, run_hook
from test_m2_adapters import check


class M3(unittest.TestCase):
    def test_replay_via_subprocess(self):
        for h in HARNESSES:
            with self.subTest(h=h):
                w = tmpdir(self)
                d = None
                for event, payload in iter_payloads(h, w):
                    r = run_hook(h, event, payload, {"NT_SYNC": "1"})
                    self.assertEqual(r.returncode, 0)
                    expected = getattr(get_adapter(h), "STDOUT", {}).get(event)
                    if expected:
                        self.assertEqual(json.loads(r.stdout), json.loads(expected))
                    else:
                        self.assertEqual(r.stdout, "", (h, event))
                    d = store.session_dir(dict(payload, cwd=w))
                check(self, h, store.read_events(d))
                self.assertFalse(os.path.exists(os.path.join(d, "errors.log")))

    def test_garbage_input(self):
        w = tmpdir(self)
        for raw in ("", "not json", "[]", "null", "{\"cwd\": 5}"):
            r = subprocess.run([sys.executable, LAUNCHER, "hook", "--harness", "claude_code",
                                "--event", "PostToolUse"], input=raw, capture_output=True,
                               text=True, cwd=w, env=dict(os.environ, NT_HOME=w))
            self.assertEqual(r.returncode, 0, raw)
            self.assertEqual(r.stdout, "", raw)

    def test_unknown_harness_still_exits_zero(self):
        r = run_hook("nope", "X", {"cwd": tmpdir(self)})
        self.assertEqual(r.returncode, 0)

    def test_fast_with_detached_narrator(self):
        w = tmpdir(self)
        env = dict(os.environ)
        env.pop("NT_SYNC", None)
        run_hook("codex", "UserPromptSubmit", {"session_id": "f", "cwd": w, "prompt": "x"}, env)
        t = time.time()
        r = run_hook("codex", "Stop", {"session_id": "f", "cwd": w,
                                       "last_assistant_message": "done"}, env)
        self.assertEqual(r.returncode, 0)
        self.assertLess(time.time() - t, 2.0)  # includes interpreter start-up
        story = os.path.join(w, ".narrative", "f", "story.md")
        for _ in range(100):
            if os.path.exists(story):
                break
            time.sleep(0.05)
        self.assertTrue(os.path.exists(story))


if __name__ == "__main__":
    unittest.main()
