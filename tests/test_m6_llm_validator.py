import unittest

from narrative_trace.narrator import llm_scene, template_scene
from narrative_trace.validator import validate_scene

SCENE = {"turn": 1, "n": 3, "phase": "change", "seqs": [5], "facts": ["Edit src/Checkout.tsx"],
         "targets": ["src/Checkout.tsx"], "reasons": [], "status": "ok",
         "prompt": None, "final": None}
GOOD = "I edited src/Checkout.tsx to point the button at the right handler."
GOOD_PT = "Editei src/Checkout.tsx."


def fake(*answers):
    seq = list(answers)

    def call(system, user):
        a = seq.pop(0)
        if isinstance(a, Exception):
            raise a
        return a
    return call


class M6(unittest.TestCase):
    def test_good(self):
        self.assertEqual(llm_scene(SCENE, "", "en", fake(GOOD)), (GOOD, "llm"))

    def test_hallucinated_path_then_fixed(self):
        bad = "I edited src/Payment.tsx."
        self.assertFalse(validate_scene(bad, SCENE, "en")[0])
        self.assertEqual(llm_scene(SCENE, "", "en", fake(bad, GOOD)), (GOOD, "llm"))
        text, src = llm_scene(SCENE, "", "en", fake(bad, bad))
        self.assertEqual(src, "template_fallback")
        self.assertEqual(text, template_scene(SCENE, "en"))

    def test_causal_without_reason(self):
        self.assertFalse(validate_scene("I changed src/Checkout.tsx because it was broken.",
                                        SCENE, "en")[0])
        self.assertFalse(validate_scene("Alterei src/Checkout.tsx porque estava quebrado.",
                                        SCENE, "pt")[0])
        self.assertTrue(validate_scene(GOOD_PT, SCENE, "pt")[0])

    def test_list_rejected(self):
        self.assertFalse(validate_scene("- edited src/Checkout.tsx", SCENE, "en")[0])
        self.assertFalse(validate_scene("1. edited src/Checkout.tsx", SCENE, "en")[0])

    def test_must_name_target(self):
        self.assertFalse(validate_scene("I changed a file.", SCENE, "en")[0])

    def test_exception_falls_back(self):
        text, src = llm_scene(SCENE, "", "en", fake(RuntimeError("down")))
        self.assertEqual(src, "template_fallback")
        self.assertEqual(text, template_scene(SCENE, "en"))


if __name__ == "__main__":
    unittest.main()
