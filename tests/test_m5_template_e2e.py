import os
import unittest

from helpers import HARNESSES, tmpdir
from narrative_trace import store
from narrative_trace.demo import replay
from narrative_trace.narrator import TITLES, narrate_all
from narrative_trace.validator import CAUSAL

def read(p, mode="r"):
    kw = {} if "b" in mode else {"encoding": "utf-8"}
    with open(p, mode, **kw) as f:
        return f.read()


PHASES = ["mission", "investigate", "change", "setback", "change", "verify", "closing"]


class M5(unittest.TestCase):
    def run_lang(self, lang):
        old = os.environ.get("NT_LANG")
        os.environ["NT_LANG"] = lang
        self.addCleanup(lambda: os.environ.__setitem__("NT_LANG", old) if old
                        else os.environ.pop("NT_LANG", None))
        for k in ("NT_LLM_URL", "NT_LLM_MODEL"):
            os.environ.pop(k, None)
        idx = 1 if lang == "en" else 0
        for h in HARNESSES:
            with self.subTest(h=h, lang=lang):
                d = replay(h, tmpdir(self), {"NT_LANG": lang})
                story_path = os.path.join(d, "story.md")
                story = read(story_path)
                pos = -1
                for i, ph in enumerate(PHASES, 1):
                    label = "**Scene %d: %s**" % (i, TITLES[ph][idx])
                    self.assertGreater(story.find(label), pos, label)
                    pos = story.find(label)
                for target in ("src/Checkout.tsx", "handleCheckout", "npm test"):
                    self.assertIn(target, story)
                self.assertIn("<sub>events #2-#3</sub>", story)
                self.assertIn("1 failed: Checkout.test.tsx expected label Pay (exit 1)", story)
                rows = store.read_jsonl(os.path.join(d, "scenes.jsonl"))
                self.assertTrue(all(r["source"] == "template" for r in rows))
                before = read(story_path, "rb")
                narrate_all(d)
                self.assertEqual(read(story_path, "rb"), before)
                self.assertEqual(len(store.read_jsonl(os.path.join(d, "scenes.jsonl"))), 7)

    def test_pt(self):
        self.run_lang("pt")

    def test_en(self):
        self.run_lang("en")

    def test_no_invented_causes(self):
        d = replay("codex", tmpdir(self), {"NT_LANG": "en"})
        for r in store.read_jsonl(os.path.join(d, "scenes.jsonl")):
            if r["phase"] in ("mission", "closing"):
                continue  # quoted human/agent words
            for w in CAUSAL["en"]:
                self.assertNotIn(w, r["text"].lower())


if __name__ == "__main__":
    unittest.main()


class MultiTurn(unittest.TestCase):
    def test_two_turns_same_session(self):
        w = tmpdir(self)
        replay("codex", w)
        d = replay("codex", w)
        story = read(os.path.join(d, "story.md"))
        self.assertIn("## Turn 1", story)
        self.assertIn("## Turn 2", story)
        rows = store.read_jsonl(os.path.join(d, "scenes.jsonl"))
        self.assertEqual([r["turn"] for r in rows], [1] * 7 + [2] * 7)
        self.assertEqual(rows[7]["seqs"], [10])
