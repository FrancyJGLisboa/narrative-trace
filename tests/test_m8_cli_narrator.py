import json
import os
import stat
import tempfile
import unittest

from narrative_trace import cli, cli_llm, narrator, store
from tests.helpers import *  # noqa: F401,F403


class CliNarratorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.fake = os.path.join(self.tmp, "fakellm.sh")
        with open(self.fake, "w") as f:
            f.write("#!/bin/sh\ncat >/dev/null\necho \"I read a.py.\"\n")
        os.chmod(self.fake, os.stat(self.fake).st_mode | stat.S_IEXEC)
        self.old = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old)

    def test_custom_command_is_the_narrator_without_api_key(self):
        os.environ.pop("NT_LLM_URL", None)
        os.environ["NT_LLM_CMD"] = self.fake
        self.assertTrue(narrator.llm_enabled())
        self.assertEqual(cli_llm.make_call()("sys", "user").strip(), "I read a.py.")

    def test_child_gets_guard_and_neutral_cwd(self):
        probe = os.path.join(self.tmp, "probe.sh")
        with open(probe, "w") as f:
            f.write("#!/bin/sh\ncat >/dev/null\necho \"$NT_NARRATING $PWD\"\n")
        os.chmod(probe, 0o755)
        os.environ["NT_LLM_CMD"] = probe
        out = cli_llm.make_call()("s", "u").split()
        self.assertEqual(out[0], "1")
        self.assertNotEqual(os.path.realpath(out[1]), os.path.realpath(os.getcwd()))

    def test_hook_is_silent_while_narrating(self):
        os.environ["NT_NARRATING"] = "1"
        os.environ["NT_HOME"] = self.tmp
        a = type("A", (), {"harness": "claude_code", "event": "UserPromptSubmit"})()
        self.assertEqual(cli.cmd_hook(a), 0)
        self.assertEqual(os.listdir(self.tmp).count("state.json"), 0)

    def test_unknown_name_is_rejected(self):
        os.environ["NT_LLM"] = "nope"
        with self.assertRaises(ValueError):
            cli_llm._argv(cli_llm.pick(), "s", self.tmp)


if __name__ == "__main__":
    unittest.main()
