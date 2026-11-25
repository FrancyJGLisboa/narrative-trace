# Narrative Trace

Every time you press Enter, your AI coding agent goes on a small journey: it reads files, forms a plan,
edits, breaks something, fixes it, and finishes. Most harnesses show you either a spinner or a wall of
logs, so the journey disappears and you are left owning code you cannot explain.

Narrative Trace listens to your harness through its official hooks and writes that journey as a
**chronological sequence of scenes, narrated in first person by the agent**, in `story.md`:

```markdown
**Scene 3: The change**
I changed src/Checkout.tsx. The reason I recorded: "The onClick calls handleCheckoutOld, which no
longer exists. I will point it to handleCheckout."
<sub>events #4-#5</sub>

**Scene 4: Setback**
Something went wrong: Bash npm test: 1 failed: Checkout.test.tsx expected label Pay (exit 1).
<sub>events #6</sub>
```

It works with **Claude Code, Codex CLI, Gemini CLI and Cursor**, plus anything that can send JSON
events (custom loops, OpenTelemetry exporters) through the `generic` adapter.

## Install (one line)

macOS / Linux / WSL:

```sh
curl -fsSL https://raw.githubusercontent.com/FrancyJGLisboa/narrative-trace/main/install.sh | sh
```

Windows (PowerShell):

```powershell
irm https://raw.githubusercontent.com/FrancyJGLisboa/narrative-trace/main/install.ps1 | iex
```

Or with pipx: `pipx install git+https://github.com/FrancyJGLisboa/narrative-trace && narrative-trace install`

By default the installer detects which harnesses you have and registers hooks at **user level**, so every
project gets a story. Options:

```sh
curl -fsSL .../install.sh | sh -s -- --harness cursor --scope project   # one harness, this repo only
```

On Windows set `$env:NT_HARNESS` / `$env:NT_SCOPE` before running the one-liner.

After installing, follow the one-line note printed for each harness: start a new Claude Code session,
trust the hooks in Codex with `/hooks`, accept Gemini CLI's trust prompt, restart Cursor.

Requirements: Python 3.9 or newer. No other dependencies.

## Where the story is

`<project>/.narrative/<session-id>/story.md` (set `NT_HOME` to put stories somewhere else).
Add `.narrative/` to your `.gitignore`, or commit the stories next to your code if you want the history.

Each session folder also has `trace.jsonl` (the raw, immutable chronology), `scenes.jsonl` and
`errors.log` (if anything went wrong inside the hooks).

## How it works

```
harness hooks ──> adapter ──> trace.jsonl ──> scene chunker ──> narrator ──> story.md
(native JSON)    (per harness)  (seq-numbered)   (deterministic)   (template or LLM + validator)
```

1. **Zero interference.** Hooks always exit 0, print nothing the harness would act on, and hand the
   narration to a detached background process. The agent never waits for the story.
2. **Chronology from the system, not from a model.** Every event gets a sequence number under a file
   lock. Scenes cite the events they come from.
3. **No invented motives.** The agent's reasons come from its own words where the harness exposes them
   (Claude Code transcript, Cursor responses, the final message in Codex and Gemini CLI). If no reason was
   recorded, the scene says only what happened.
4. **Works without any LLM, and without an API key.** The default narrator is a deterministic template.
   To get prose from the model you already pay for, point it at your subscription CLI:

   ```sh
   export NT_LLM=auto        # uses the CLI of the harness you are in (claude, codex, ...)
   export NT_LLM=claude      # or: codex | copilot | gemini   (copilot and gemini are not yet verified)
   export NT_LLM_CMD="my-cli --flag"   # any command: prompt on stdin, scene text on stdout
   ```

   One model call narrates a whole turn (up to 12 scenes per call). A scene the model gets wrong is asked again alone, and then falls back to the template.
   The narrator runs in the background after your turn, in a neutral folder, with a guard variable so its own
   hooks stay silent. It uses a little of your subscription per scene. If you do have an endpoint, the
   OpenAI-compatible mode still works (`NT_LLM_URL`, `NT_LLM_MODEL`, `NT_LLM_KEY`).

   Every LLM scene goes through a validator that rejects file names not in the events, explanations
   without a recorded reason, and list formatting. Two rejections fall back to the template.

Language: `NT_LANG=pt` (default) or `NT_LANG=en`.

## Commands

```sh
narrative-trace install   --harness auto|all|claude_code|codex|gemini_cli|cursor --scope user|project [--dry-run]
narrative-trace uninstall --harness all --scope user
narrative-trace demo --harness claude_code --out ./narrative-demo     # see a sample story right now
narrative-trace narrate --session-dir .narrative/<id> --all          # rebuild a story
```

(From a clone, `python ntrace.py ...` works the same.)

## Learning notes

For people who are new to code, a scene can carry a line `> Para entender: ...` (`To understand:` in English). It explains one concept in plain words, once per session: reading a file, editing, a command, a test, installing, git, a failure. The texts are written by hand in `narrative_trace/lessons.py`, never by a model, so they cannot invent facts about your session. They explain the idea, not the agent's motive. `NT_LESSONS=off` hides them.

## Known limits

- The glossary has 9 concepts and is not adaptive. A concept it does not know gets no note.

- Scenes quote what an edit changed (before and after, cut to 160 characters, secrets redacted) for Claude Code, Gemini CLI and any harness whose edit payload has old/new strings or file content. Codex patches and Cursor edits show the file name only. The snippets are stored in `trace.jsonl`, which stays on your machine.
- The LLM narrator may add small claims the events do not hold (for example "that was the only change"). The validator checks file names and reasons, not every phrase.

- Verified live with Claude Code and Codex as narrator (subscription, no key). Copilot CLI and Gemini CLI narrator commands are written from docs and untested. There is no Copilot CLI hook adapter yet.
- Codex still reads your global `~/.codex/AGENTS.md`, so your own style rules can leak into scenes.

- How much "why" you get depends on the harness: full in Claude Code (transcript), per response in
  Cursor, final message only in Codex and Gemini CLI.
- Hook payloads were checked against each vendor's documentation (November 2026), and the test suite
  replays those documented shapes. A live run in each harness is still the real test: if a story looks
  wrong, look at `trace.jsonl` and `errors.log`, and open an issue.
- Internal tool names of Cursor and Codex are not fully documented; unknown tools land in an
  "Other actions" scene instead of breaking anything.
- Hosted tools that do not fire tool hooks (for example Codex web search) never appear in the story.

## The build prompt

[`prompt/BUILD_PROMPT.md`](prompt/BUILD_PROMPT.md) (same text in `prompt/TEXTO.txt`) is a complete,
decision-free specification that lets a coding agent, including small models, rebuild this system from
scratch with milestone tests and fixed ground truth. Version 2 incorporates everything learned while
implementing this repository and verifying the hook payloads.

## Development

```sh
python -m unittest discover -s tests -v     # 31 tests, standard library only
python tools/gen_examples.py                # regenerate the example sessions
```

## Em português

Narrative Trace transforma cada Enter que você aperta no seu agente de IA numa sequência de cenas
narradas em primeira pessoa pelo próprio agente, em ordem cronológica, para que você entenda e consiga
explicar o que foi feito. Instalação em uma linha (acima), funciona com Claude Code, Codex CLI, Gemini CLI
e Cursor, e o padrão de narração é em português (`NT_LANG=pt`).

## License

MIT
