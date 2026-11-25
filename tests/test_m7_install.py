import io
import json
import os
import unittest

from helpers import HARNESSES, tmpdir
from narrative_trace.adapters import get_adapter
from narrative_trace.install import LAUNCHER, config_path, install, uninstall


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def commands(cfg):
    out = []
    for ev, groups in cfg.get("hooks", {}).items():
        for g in groups:
            if "command" in g:
                out.append((ev, g["command"]))
            for h in g.get("hooks", []):
                out.append((ev, h["command"]))
    return out


class M7(unittest.TestCase):
    def test_install_each(self):
        for h in HARNESSES:
            with self.subTest(h=h):
                proj = tmpdir(self)
                p = config_path(h, proj, "project")
                os.makedirs(os.path.dirname(p))
                with open(p, "w") as f:
                    json.dump({"keep": 1, "hooks": {"Other": [{"command": "x"}]}}, f)
                install(h, proj, out=io.StringIO())
                install(h, proj, out=io.StringIO())  # idempotent
                cfg = load(p)
                self.assertEqual(cfg["keep"], 1)
                self.assertIn("Other", cfg["hooks"])
                self.assertTrue(os.path.exists(p + ".bak"))
                ours = [c for c in commands(cfg) if "narrative_trace" in c[1]]
                self.assertEqual(sorted(e for e, _ in ours), sorted(get_adapter(h).EVENTS))
                for ev, cmd in ours:
                    self.assertIn(LAUNCHER, cmd)
                    self.assertTrue(cmd.endswith("--harness %s --event %s" % (h, ev)))
                if h == "cursor":
                    self.assertEqual(cfg["version"], 1)
                uninstall(h, proj, out=io.StringIO())
                cfg = load(p)
                self.assertEqual([c for c in commands(cfg) if "narrative_trace" in c[1]], [])
                self.assertIn("Other", cfg["hooks"])

    def test_dry_run(self):
        proj = tmpdir(self)
        buf = io.StringIO()
        p = install("claude_code", proj, dry_run=True, out=buf)
        self.assertFalse(os.path.exists(p))
        self.assertIn("UserPromptSubmit", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
