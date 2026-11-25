# BUILD PROMPT v2: Narrative Trace (harness-agnostic, first-person scene narration for AI agents)

> v2 is the refined version of this prompt, rewritten after a full end-to-end implementation
> (github.com/FrancyJGLisboa/narrative-trace) and after checking every hook payload against the
> official documentation of Claude Code, Codex CLI, Gemini CLI and Cursor (November 2026).
> Everything marked VERIFIED comes from those docs. Hook APIs change: re-check them if this is old.

You are a coding agent. Build the system specified below, end to end, with no human help.
This spec is written so that every design decision is already made. Your job is to implement it
exactly, verify each milestone with the tests listed, and stop only when the Definition of Done is met
or when the BLOCKED rule applies.

---

## 0. RULES YOU MUST FOLLOW (read twice)

1. Work one milestone at a time, in order. Do not start milestone N+1 until every test of milestone N passes.
2. After writing code for a milestone, run: `python -m unittest discover -s tests -v`. Read the output. Fix failures. Repeat.
3. Python 3.9+ standard library ONLY. No pip installs. No third-party imports.
4. Copy every literal string, file name, JSON key, and template in this spec VERBATIM.
5. Never change the GROUND TRUTH sections (Section 9) to make a test pass. Change the code instead.
6. Never weaken, skip, or delete a test to make it pass.
7. Keep each source file under 250 lines. If a file grows past that, split it.
8. BLOCKED rule: if the same test fails 3 times in a row after 3 different fix attempts, write `BLOCKED.md`
   containing the test name, the full error, and the 3 attempts. Then stop. Never fake a pass.
9. Do not invent features. Do not rename anything. Do not add configuration options not listed here.
10. When finished, write `REPORT.md` (Section 11).

---

## 1. WHAT THE SYSTEM DOES (context, do not skip)

AI coding agents (Claude Code, Codex CLI, Gemini CLI, Cursor, and others) run tools in a loop when a human
presses Enter. The human usually sees either a spinner or raw logs, and loses the story of what happened.

Narrative Trace listens to the harness through its hooks, records every event in strict chronological order,
groups events into scenes, and writes each scene as a short first-person narration by the agent, addressed to
the human. Output goes to `story.md`.

Non-negotiable properties:
- ZERO interference: hooks never block, never modify, never slow down the agent. Hooks always exit 0 and print
  nothing to stdout (one exception for Cursor, Section 5.4).
- Chronology comes from the event log, never from an LLM's memory.
- Fidelity: the narration may only state facts present in the events. If the agent's reason was not recorded,
  the narration must not invent one.
- Works with no LLM at all (deterministic template narrator). An LLM narrator is optional and is guarded by a
  validator that falls back to the template on failure.

---

## 2. FILE TREE (create exactly this)

```
ntrace.py                          # launcher for a git clone: inserts its dir in sys.path, calls cli.main()
pyproject.toml                 # setuptools, console script narrative-trace = narrative_trace.cli:main,
                               # package-data narrative_trace/examples/*/*.jsonl, no dependencies
install.sh / install.ps1       # one-line installers (Section 6.2)
narrative_trace/
  __init__.py                  # __version__ = "0.1.0"
  __main__.py                  # from .cli import main; main()
  launcher.py                  # same as ntrace.py but inside the package: hook commands point HERE,
                               # so they keep working for both git clones and pip/pipx installs
  schema.py                    # make_event, redact, truncate, pick, as_text, extract_target,
                               # is_shell, summarize_error, classify_phase, EXIT_RX
  store.py                     # session_id, session_dir, session_lock, load/save_state,
                               # append_events, append_event, read_events, read_jsonl, log_error
  transcript.py                # read_new_assistant_texts() for Claude Code transcripts
  adapters/
    __init__.py                # shared builders + get_adapter(name)
    claude_code.py codex.py gemini_cli.py cursor.py generic.py
  chunker.py                   # build_scenes(events)
  narrator.py                  # TITLES, templates, template_scene, llm_scene, narrate_turn, narrate_all
  validator.py                 # validate_scene
  render.py                    # render_story
  install.py                   # install / uninstall / detect / config_path
  demo.py                      # iter_payloads, run_hook, replay, run_demo
  cli.py                       # hook | narrate | install | uninstall | demo
  examples/<harness>/payloads.jsonl (+ claude_code/transcript.jsonl)   # Section 9.4
tools/gen_examples.py          # regenerates examples/ (deterministic)
tests/  helpers.py test_m1_*.py ... test_m7_*.py
README.md  LICENSE  .gitignore (.narrative/ ignored)
```

## 3. THE NEUTRAL EVENT SCHEMA (schema.py)

Every adapter outputs zero or more events in this exact shape. One event per line in `trace.jsonl`.

```json
{
  "v": 1,
  "seq": 4,
  "ts": "2026-11-25T10:40:12.123Z",
  "session": "abc123",
  "turn": 1,
  "harness": "claude_code",
  "kind": "tool_result",
  "tool": "Edit",
  "target": "src/Checkout.tsx",
  "status": "ok",
  "summary": "Edit src/Checkout.tsx",
  "text": null
}
```

Field rules:
- `kind` is one of: `turn_start`, `tool_call`, `tool_result`, `agent_text`, `error`, `turn_end`.
- `seq` and `turn` are assigned by `store.append_event`, NOT by adapters. Adapters set them to `null`.
- `ts` is UTC ISO 8601 with milliseconds and a trailing `Z`, set by `make_event`.
- `tool`: tool name string or null. `target`: file path, command, pattern, or URL (max 200 chars) or null.
- `status`: `"ok"`, `"error"`, or null.
- `summary`: max 300 chars, built as `"{tool} {target}"` when both exist, plus `": {error_text}"` on error.
- `text`: user prompt (turn_start) or agent words (agent_text, turn_end). Max 2000 chars. Else null.

Helper functions (implement exactly):
- `pick(d, *keys, default=None)`: return the first key present in dict `d` with a non-empty value. Supports
  dotted keys like `"tool_input.file_path"`. Never raises.
- `truncate(s, n)`: if `len(s) > n`, return `s[:n-3] + "..."`. Accepts None (returns None).
- `redact(s)`: replace with `"[REDACTED]"` any match of these regexes (case-insensitive):
  `sk-[A-Za-z0-9_-]{16,}`, `ghp_[A-Za-z0-9]{20,}`, `AKIA[0-9A-Z]{16}`, `(?i)(api[_-]?key|token|secret|password)\s*[=:]\s*\S+`,
  `Bearer\s+[A-Za-z0-9._-]{16,}`. Apply `redact` to `target`, `summary`, and `text` before truncating.
- `extract_target(tool_input)`: if tool_input is a dict, return `pick(tool_input, "file_path", "path",
  "filePath", "absolute_path", "target_file", "command", "cmd", "pattern", "query", "url", "notebook_path")`
  (join lists with spaces); if it is a string, return it; else None.
- `as_text(v)`: flatten any output shape to a string. Strings as is; lists joined; dicts: first non-empty of
  `text, stderr, error, error_message, message, output, stdout, llmContent, returnDisplay, content`.
- `EXIT_RX = (?i)(?:exit(?:ed)?\s*code|process exited with code)\s*:?\s*(-?\d+)`.
- `is_shell(tool)`: lowercase tool is in `{bash, shell, run_shell_command, shell_command, exec, terminal,
  local_shell, exec_command, run_terminal_cmd, run_terminal_command, powershell}` or contains `shell`,
  `terminal`, `bash` or `powershell`.
- `summarize_error(text)`: one informative line. Drop empty lines and lines starting with `Command`,
  `Directory`, `Wall time`, `Duration`, `Exit code`, `Process exited`; strip leading `Output:`, `Stdout:`,
  `Stderr:` (keep `Error:`, it carries meaning); prefer the first line matching
  `fail|error|exception|traceback|not found`, else the first line; append ` (exit N)` when EXIT_RX finds N != 0.
  Example: `"Exit code 1\nError: Cannot find module 'express'"` -> `"Error: Cannot find module 'express' (exit 1)"`.
- `make_event(...)`: on error, summary is `"{tool} {target}: {summarize_error(error_text)}"`.
- `classify_phase(event)` (used by the chunker), applied to `tool_result` and `tool_call` events:
  - Lowercase `tool` and `target`.
  - If `is_shell(tool)`: `"investigate"` when the command starts with a read-only command
    (`cat head tail less more rg grep ag ls tree find fd wc stat file nl`, `sed -n`,
    `git diff|log|show|status|blame|grep`), because agents like Codex read files through the shell;
    otherwise the verify/run rules below.
  - `"verify"` if tool is a shell tool AND target matches regex
    `\b(test|tests|pytest|jest|vitest|mocha|unittest|cargo test|go test|npm test|pnpm test|yarn test|build|lint|tsc|mypy|ruff)\b`.
  - `"run"` if tool is a shell tool and neither of the above.
  - `"change"` if tool contains any of: `write`, `edit`, `patch`, `replace`, `create`, `delete`, `apply`, `multiedit`.
  - `"investigate"` if tool contains any of: `read`, `grep`, `glob`, `search`, `list`, `ls`, `find`, `fetch`, `web`, `view`, `open`.
  - else `"other"`.

---

## 4. STORAGE (store.py)

- Base dir: env `NT_HOME` if set, else `<project>/.narrative/`, where project = `pick(payload, "cwd")`, else
  first item of `payload["workspace_roots"]`, else `os.getcwd()`.
- Session dir: `<base>/<session_id>/`. Session id = `pick(payload, "session_id", "sessionId", "conversation_id",
  "conversationId", "thread_id")`, else `"default"`. Sanitize to `[A-Za-z0-9_-]`, max 64 chars.
- Files in session dir: `trace.jsonl`, `state.json`, `scenes.jsonl`, `story.md`, `errors.log`, `lock`.
- `state.json` default: `{"current_turn": 0, "last_seq": 0, "cc_transcript_offset": 0, "narrated_turns": []}`.
- Locking (cross-platform, stdlib only): acquire by `os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)`.
  If it exists, retry every 20 ms for up to 3 seconds. If the lock file is older than 10 seconds, delete it and
  retry (stale lock). Release by closing and deleting. Use a context manager `with session_lock(dir):`.
- `append_event(session_dir, event)`: under the lock, load state; if `kind == "turn_start"`, increment
  `current_turn`; set `event["turn"] = current_turn` (minimum 1); set `event["seq"] = last_seq + 1`; append one
  JSON line (`json.dumps(event, ensure_ascii=False)`) to `trace.jsonl`; save state. Return the event.
- `read_events(session_dir, turn=None)`: return events sorted by `seq`, optionally filtered by turn. Skip
  malformed lines silently.

---

## 5. ADAPTERS

Each adapter module exposes `EVENTS` (the tuple of events the installer registers), optionally `STDOUT`
(event -> exact string the hook must print), and:

```python
def to_events(event_name: str, payload, session: str, state: dict) -> list[dict]:
```

`session` is the session id. `state` is the session state dict; an adapter may update
`state["cc_transcript_offset"]` and the CLI persists it inside the same lock as the events.
The event name comes from the CLI argument `--event` (written into the harness config by the installer), so
adapters never depend on a payload field for it. Unknown event names return `[]`. Adapters must never raise:
wrap the body in try/except and return `[]` on any exception.

Tolerant field names (use `pick` with these, in this order):
- tool name: `"tool_name", "toolName", "tool"`
- tool input: `"tool_input", "toolInput", "input", "args", "arguments"`
- tool output: `"tool_response", "toolResponse", "tool_output", "output", "result"`
  (if the value is a string that starts with `{` or `[`, try `json.loads` on it: Cursor stringifies it)
- error: `"error", "tool_error", "error_message", "errorMessage"`
- prompt: `"prompt", "user_prompt", "userPrompt", "text", "message"`
- agent words: `"last_assistant_message", "prompt_response", "response", "text", "thought", "message"`

Status of a tool result is `"error"` if: an error field is non-empty; or the output is a dict with
`is_error`/`isError` true, `success` false, non-zero `exit_code`/`exitCode`, or a non-empty `error`; or the
payload has a non-zero `exit_code`/`exitCode`; or the tool is a shell tool and EXIT_RX finds a non-zero code in
the first 4000 chars of `as_text(output)` (Codex and Gemini report shell exit codes as text). A non-shell tool
whose output merely mentions "exit code 1" stays `"ok"`. Failure events (`PostToolUseFailure`,
`postToolUseFailure`) are always `"error"`.

### 5.1 claude_code.py (VERIFIED)

Common payload fields: `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `permission_mode`.

| --event | Payload extras | Emits |
|---|---|---|
| `UserPromptSubmit` | `prompt` | read the transcript only to advance the offset, then `turn_start` |
| `PostToolUse` | `tool_name`, `tool_input`, `tool_response`, `tool_use_id` | new transcript `agent_text`s, then `tool_result` |
| `PostToolUseFailure` | `tool_name`, `tool_input`, `error` (e.g. `"Exit code 1\n..."`), `is_interrupt` | new transcript `agent_text`s, then `tool_result` status error |
| `Stop` | `last_assistant_message` | new transcript `agent_text`s, then `last_assistant_message` as `agent_text` unless identical to one already emitted, then `turn_end` |

A non-zero Bash exit fires `PostToolUseFailure`, NOT `PostToolUse`. Plain stdout on `UserPromptSubmit` is
injected into the model context, so the hook must print nothing.

Transcript reading (`transcript.py`): `read_new_assistant_texts(path, offset) -> (texts, new_offset)`.
Read all lines; if `offset > len(lines)` restart at 0 (new file or compaction). From line `offset` on, for each
JSON line with `type == "assistant"`, collect `message.content` blocks with `type == "text"` (or the content
itself if it is a string). Return texts and `len(lines)`. Any error: `([], offset)`. Reading at every
PostToolUse is what keeps the agent's reasons in true chronological position.

### 5.2 codex.py (VERIFIED)

Hooks are on by default (disable with `[features] hooks = false`). Files: `~/.codex/hooks.json` (user) and
`.codex/hooks.json` (trusted project). New hooks must be trusted by the user via `/hooks`.

| --event | Payload extras | Emits | Stdout |
|---|---|---|---|
| `UserPromptSubmit` | `prompt`, `turn_id` | `turn_start` | nothing |
| `PostToolUse` | `tool_name`, `tool_input`, `tool_response` | `tool_result` | nothing |
| `Stop` | `last_assistant_message` (string or null) | `agent_text` if present, then `turn_end` | `{}` (Stop requires JSON) |

### 5.3 gemini_cli.py (VERIFIED)

Gemini CLI parses stdout as JSON for every hook: print `{}` for all three events.

| --event | Payload extras | Emits |
|---|---|---|
| `BeforeAgent` | `prompt` | `turn_start` |
| `AfterTool` | `tool_name`, `tool_input`, `tool_response` = `{llmContent, returnDisplay, error?}` | `tool_result` |
| `AfterAgent` | `prompt`, `prompt_response` | `agent_text` from `prompt_response`, then `turn_end` |

### 5.4 cursor.py (VERIFIED)

Common fields: `conversation_id`, `generation_id`, `hook_event_name`, `workspace_roots`, `transcript_path`.

| --event | Payload extras | Emits | Stdout |
|---|---|---|---|
| `beforeSubmitPrompt` | `prompt`, `attachments` | `turn_start` | `{"continue": true}` |
| `postToolUse` | `tool_name`, `tool_input`, `tool_output` (JSON string), `tool_use_id` | `tool_result` | nothing |
| `postToolUseFailure` | `tool_name`, `tool_input`, `error_message`, `failure_type`, `is_interrupt` | `tool_result` error | nothing |
| `afterAgentResponse` | `text` | `agent_text` | nothing |
| `stop` | `status`, `loop_count` | `turn_end` | nothing |

Do NOT install `afterFileEdit` / `afterShellExecution`: they duplicate `postToolUse` and
`afterShellExecution` has no exit code. The adapter may still map them (tool `"Edit"` with `file_path`,
tool `"Shell"` with `command`) for users who add them by hand.

### 5.5 generic.py

For any harness or framework that can already write the neutral schema (an OpenTelemetry exporter, a custom
loop): `--event` is ignored; the payload is one neutral event, a list of them, or `{"events": [...]}`.
Keep items whose `kind` is valid, rebuild them with `make_event` (redaction and truncation apply).

## 6. CLI (cli.py)

```
python ntrace.py hook --harness <name> --event <EventName>      # reads JSON payload from stdin
python ntrace.py narrate --session-dir <dir> [--turn N | --all]
python ntrace.py install   --harness <name|all|auto> [--project <dir>] [--scope project|user] [--dry-run]
python ntrace.py uninstall --harness <name|all|auto> [--project <dir>] [--scope project|user]
python ntrace.py demo --harness <name> --out <dir>              # replays narrative_trace/examples/<name>, narrates
```

`hook` command contract (this is the most important function in the system):
1. Wrap EVERYTHING in `try: ... except BaseException:` and in the except branch append the traceback to
   `errors.log` if a session dir is known. Always `sys.exit(0)`.
2. Read stdin fully. Empty or invalid JSON: treat payload as `{}`.
3. Print the adapter `STDOUT` string for this event if defined (do this FIRST, before any work that could
   fail), else print nothing.
4. Resolve session dir, load state, call the adapter, then `append_events(dir, events, state_updates)` which
   assigns seq/turn and saves the new `cc_transcript_offset` in ONE locked operation.
5. If any emitted event has `kind == "turn_end"`, start the narrator in a DETACHED background process and return
   immediately: `subprocess.Popen([sys.executable, <abs path to ntrace.py>, "narrate", "--session-dir", d, "--turn", str(turn)],
   stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL, start_new_session=True)` on POSIX; on Windows use
   `creationflags=0x00000008 | 0x00000200` (DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP) instead of
   `start_new_session`. Environment variable `NT_SYNC=1` makes it run narrate inline instead (used by tests).
   The narrator path must be `narrative_trace/launcher.py`, never a path that only exists in a git clone.
6. Must complete in about the time of a Python start-up when the narrator is detached.

### 6.1 Installer rules

- Hook command: `"<sys.executable>" "<abs path to narrative_trace/launcher.py>" hook --harness <h> --event <E>`.
- Config files: project scope `.claude/settings.json`, `.codex/hooks.json`, `.gemini/settings.json`,
  `.cursor/hooks.json`; user scope the same under `~/`.
- Merge, never overwrite: load existing JSON, remove previous entries whose JSON contains `narrative_trace`,
  append fresh ones, keep every other key and hook. Copy the old file to `<file>.bak` before writing.
- `auto` = harnesses whose config dir exists (project or home) or whose binary is on PATH
  (`claude`, `codex`, `gemini`, `cursor`/`cursor-agent`).
- After installing, print one note per harness: Claude Code new session or `/hooks`; Codex `/hooks` to trust;
  Gemini trusts project hooks on first run; Cursor restart.

### 6.2 One-line installers

- `install.sh` (macOS/Linux/WSL): find Python 3.9+, `git clone --depth 1` (or download the tarball) into
  `~/.narrative-trace`, then `python ntrace.py install --harness auto --scope user`. Accept `--harness`/`--scope`.
- `install.ps1` (Windows): same, with `py -3`/`python`, zip download fallback, options via
  `$env:NT_HARNESS` / `$env:NT_SCOPE`.
- Also support `pipx install git+<repo>` followed by `narrative-trace install`.

---

## 7. CHUNKER (chunker.py)

`build_scenes(events)` takes the events of ONE turn, sorted by seq, and returns a list of scene dicts:

```json
{"turn": 1, "n": 2, "phase": "investigate", "seqs": [2, 3],
 "facts": ["Read src/Checkout.tsx", "Grep handleCheckout"], "targets": ["src/Checkout.tsx", "handleCheckout"],
 "reasons": [], "status": "ok", "prompt": null, "final": null}
```

Algorithm (deterministic, implement exactly):
1. `turn_start` creates scene phase `"mission"` with `prompt = text`, then closes it immediately.
2. `agent_text` is held in a `pending_reasons` buffer with its seq. Do not open a scene for it.
3. For each `tool_result` (and `tool_call` if no matching result exists): compute `phase = classify_phase(e)`.
   - If `status == "error"`: close the current scene; create a scene with phase `"setback"` containing only
     this event; attach pending reasons to it; close it.
   - Else if there is an open scene with the same phase, fewer than 8 events, AND no pending reasons: add the
     event to it. (New agent words always start a new scene, so a reason is never glued onto actions that
     happened before it was said.)
   - Else close the open scene and open a new scene with this phase, attaching all pending reasons (and their
     seqs) to it, then add the event.
4. `turn_end`: close the open scene. Create a scene phase `"closing"` with `final` = the text of the LAST
   pending agent_text (if any) and seqs = all remaining pending agent_text seqs plus the turn_end seq.
   Earlier pending reasons, if any, go into this scene's `reasons`.
5. `error` kind events become their own `"setback"` scene.
6. Number scenes `n = 1, 2, 3...` in creation order. `status` of a scene is `"error"` if any event in it errored.
7. `targets` is the ordered unique list of non-null targets. `facts` is the list of summaries.

---

## 8. NARRATOR (narrator.py) AND VALIDATOR (validator.py)

Language: env `NT_LANG`, `"pt"` or `"en"`, default `"pt"`.

### 8.1 Template narrator (deterministic, no LLM)

Scene title by phase:

| phase | pt | en |
|---|---|---|
| mission | A missão | The mission |
| investigate | Investigação | Investigation |
| change | A mudança | The change |
| setback | O tropeço | Setback |
| verify | O veredito | The verdict |
| run | Execução | Running |
| closing | O desfecho | Closing |
| other | Outras ações | Other actions |

Scene text (`{targets}` = targets joined by `", "`; `{first_fact}` = facts[0]):

| phase | pt | en |
|---|---|---|
| mission | `Você me pediu: "{prompt}". Comecei a trabalhar nisso.` | `You asked me: "{prompt}". I started working on it.` |
| investigate | `Fui investigar: consultei {targets}.` | `I investigated: I looked at {targets}.` |
| change | `Alterei {targets}.` | `I changed {targets}.` |
| setback | `Algo deu errado: {first_fact}.` | `Something went wrong: {first_fact}.` |
| verify (ok) | `Rodei a verificação ({targets}) e ela passou.` | `I ran the check ({targets}) and it passed.` |
| run | `Executei {targets}.` | `I ran {targets}.` |
| closing (final) | `Terminei. Minhas palavras finais: "{final}"` | `I finished. My final words: "{final}"` |
| closing (no final) | `Terminei este turno.` | `I finished this turn.` |
| other | `Executei: {targets}.` | `I did: {targets}.` |

If the scene has reasons, append to any phase: pt ` O motivo que registrei: "{reasons[0]}"` / en
` The reason I recorded: "{reasons[0]}"`. Truncate inserted prompt/final/reason to 300 chars.

### 8.2 LLM narrator (optional)

Enabled only if env `NT_LLM_URL` and `NT_LLM_MODEL` are set. Use an OpenAI-compatible
`POST {NT_LLM_URL}/chat/completions` via `urllib.request`, header `Authorization: Bearer {NT_LLM_KEY}` if that
env var is set, timeout 20 s, `temperature: 0.2`, `max_tokens: 300`. Read `choices[0].message.content`.
This works with any server that speaks that API (local or hosted).

System prompt (verbatim, with `{LANG}` replaced by `Brazilian Portuguese` or `English`):

```
You are the AI agent that performed the actions below. Narrate your own work to the human, in first person, in {LANG}.
Write ONE scene: 1 to 4 sentences of plain prose. No headings, no lists, no markdown.
Rules:
1. Use only the FACTS, TARGETS, REASONS, PROMPT and FINAL given. Add no other facts.
2. Write every file name, command and identifier exactly as given.
3. If REASONS is empty, do not explain why you did anything. Say only what happened.
4. Do not invent emotions or physical sensations. A setback is described as what failed and where.
5. Do not mention events that are not listed.
Output only the scene text.
```

User message: the scene dict as JSON, plus `"previous_scene_text"` (text of the prior scene in this turn, or "").

`llm_scene(scene, prev_text, lang, call=None)`: `call` is an injectable function `(system, user) -> str` used by
tests; default is the HTTP call. Flow: call, validate; if invalid, call once more with the validator reason
appended to the user message as `"Your previous answer was rejected: {reason}. Fix it."`; if still invalid or
any exception, return `template_scene(scene, lang)` and mark `"source": "template_fallback"`.

### 8.3 Validator

`validate_scene(text, scene, lang) -> (bool, reason)`. Reject (return False with a reason) if:
1. Empty after strip, or longer than 700 characters.
2. Any line starts with `-`, `*`, `#`, or a digit followed by `.`.
3. It contains a path-like token not found in the scene's joined `facts + targets + reasons + [prompt, final]`.
   Path-like regex: `(?:[\w-]+/)+[\w.-]+|\b[\w-]+\.(?:py|ts|tsx|js|jsx|json|md|rs|go|java|rb|css|html|yml|yaml|toml|sql|sh|txt)\b`
4. The scene has targets and none of the targets' basenames appears in the text.
5. The scene has no reasons and the lowercase text contains a causal word:
   pt: `porque`, `pois`, `já que`, `por isso`; en: `because`, `since`, `so that`, `therefore`.

### 8.4 narrate_turn and rendering

`narrate_turn(session_dir, turn)`: read events for the turn, build scenes, and for each scene not already present
in `scenes.jsonl` (key = turn + n + tuple(seqs), so a scene whose events changed is rewritten) produce text (LLM if enabled, else template), then append
`{"turn", "n", "phase", "title", "text", "seqs", "source"}` to `scenes.jsonl` (`source` is `"template"`, `"llm"`,
or `"template_fallback"`). Then call `render_story`. Running it twice must not duplicate scenes.
`--all` narrates every turn present in the trace.

`render_story(session_dir)` rewrites `story.md` from `scenes.jsonl` (deterministic, byte-identical on rerun):

```
# Narrative Trace: session {session}

## Turn {turn}

**Scene {n}: {title}**
{text}
<sub>events #{first_seq}-#{last_seq}</sub>

```
(Use `#{seq}` alone when the scene has one event.)

---

## 9. GROUND TRUTH (do not edit; tests must match this)

### 9.1 Canonical scenario (all four fixtures encode this same story)

The human types: `Fix the checkout button and run the tests`. The agent then:
1. reads `src/Checkout.tsx`
2. greps `handleCheckout`
3. writes the text: `The onClick calls handleCheckoutOld, which no longer exists. I will point it to handleCheckout.`
4. edits `src/Checkout.tsx`
5. runs `npm test`, which FAILS with `1 failed: Checkout.test.tsx expected label Pay`
6. edits `src/Checkout.tsx` again
7. runs `npm test`, which passes
8. writes the final text: `Fixed: the button now calls handleCheckout and all tests pass.`
9. stops.

### 9.2 Expected neutral events after replay (same for every harness)

| seq | kind | tool (case-insensitive contains) | target | status |
|---|---|---|---|---|
| 1 | turn_start | | | |
| 2 | tool_result | read | src/Checkout.tsx | ok |
| 3 | tool_result | grep | handleCheckout | ok |
| 4 | agent_text | | | |
| 5 | tool_result | edit | src/Checkout.tsx | ok |
| 6 | tool_result | (shell tool) | npm test | error |
| 7 | tool_result | edit | src/Checkout.tsx | ok |
| 8 | tool_result | (shell tool) | npm test | ok |
| 9 | agent_text | | | |
| 10 | turn_end | | | |

Test seq 2 and 3 by phase (`investigate`) and by target containment, not by tool name: Codex reads with
`cat`/`rg` through Bash. Test seq 5 and 7 by phase `change`, and seq 6 and 8 with `is_shell(tool)`.

Harness exception you must encode in the tests:
- Codex and Gemini CLI only expose the final agent text, so they have no seq 4 agent_text: their sequence is
  9 events and every later seq shifts down by one. Their change scene therefore has `reasons == []`.

### 9.3 Expected scenes (Claude Code and Cursor)

| n | phase | seqs | reasons |
|---|---|---|---|
| 1 | mission | [1] | [] |
| 2 | investigate | [2, 3] | [] |
| 3 | change | [4, 5] | [the step 3 text] |
| 4 | setback | [6] | [] |
| 5 | change | [7] | [] |
| 6 | verify | [8] | [] |
| 7 | closing | [9, 10] | [] , final = the step 8 text |

Codex and Gemini CLI: same 7 phases in the same order, change scene 3 has seqs `[4]` and no reasons.

### 9.4 Fixture format

`narrative_trace/examples/<harness>/payloads.jsonl`: one object per line:
`{"event": "<EventName>", "payload": {...}, "transcript_upto": <int or null>}`.
`demo.replay(harness, workdir)`: for each line, if `transcript_upto` is an int, write the first N lines of
`transcript.jsonl` to `workdir/transcript.jsonl` (a transcript that grows in real time); replace `"{TRANSCRIPT}"`
and `"{CWD}"` in the payload; run the real hook command as a subprocess with `NT_SYNC=1`. Return the session dir.

Payloads per harness (use these field shapes, they are the VERIFIED ones):
- Claude Code (`session_id: fx1`, `cwd`, `transcript_path`): UserPromptSubmit(prompt, upto 1); PostToolUse Read
  (upto 3); PostToolUse Grep (upto 5); PostToolUse Edit (upto 8); **PostToolUseFailure** Bash `npm test` with
  `error: "Exit code 1\n1 failed: Checkout.test.tsx expected label Pay"` (upto 10); PostToolUse Edit (upto 12);
  PostToolUse Bash `npm test` (upto 14); Stop with `last_assistant_message` (upto 15). Transcript: 15 lines,
  the step 3 text at line 6 and the step 8 text at line 15 as assistant `text` blocks.
- Codex (`fx2`): Bash `cat src/Checkout.tsx`; Bash `rg handleCheckout`; Edit; Bash `npm test` with
  `tool_response: "Exit code: 1\nOutput:\n1 failed: ..."`; Edit; Bash `npm test` with `"Exit code: 0..."`;
  Stop with `last_assistant_message`.
- Gemini CLI (`fx3`): BeforeAgent(prompt); AfterTool `read_file` (`absolute_path`), `search_file_content`,
  `replace`, `run_shell_command` with `tool_response.llmContent: "Command: npm test\nDirectory: (root)\nOutput:
  1 failed: ...\nExit Code: 1"`, `replace`, `run_shell_command` (Exit Code: 0); AfterAgent(prompt_response).
- Cursor (`conversation_id: fx4`, `workspace_roots: ["{CWD}"]`): beforeSubmitPrompt; postToolUse `read_file`
  (`target_file`); postToolUse `grep`; afterAgentResponse(step 3 text); postToolUse `edit_file`;
  postToolUseFailure `run_terminal_cmd` with `error_message: "Exit code 1\n1 failed: ..."`; postToolUse
  `edit_file`; postToolUse `run_terminal_cmd` with `tool_output: '{"exitCode": 0, ...}'`;
  afterAgentResponse(step 8 text); stop.

The setback scene of every harness must read `... 1 failed: Checkout.test.tsx expected label Pay (exit 1)`.

## 10. MILESTONES AND ACCEPTANCE TESTS

**M0 Scaffold.** Create the tree with empty modules. Test: `python ntrace.py --help` exits 0.

**M1 Schema and store** (`test_m1_schema_store.py`):
- `pick` handles missing keys, empty values, dotted keys.
- `redact` removes a fake `sk-...` key and `password=hunter2`.
- `truncate` respects limits.
- `classify_phase` returns the expected phase for: Read, Grep, Edit, Write, Bash `npm test`, Bash `ls`, unknown tool.
- 50 appends from 10 threads produce seqs exactly 1..50 with no duplicates; turn increments on turn_start.

**M2 Adapters** (`test_m2_adapters.py`): for each of the four harnesses, replay the fixture through the adapters
directly (no subprocess) and assert the neutral event table of 9.2 (with the documented exceptions). Also:
unknown event name returns `[]`; payload `{}` does not raise.

**M3 Hook CLI** (`test_m3_hook_cli.py`):
- Replaying each fixture via subprocess gives the same events as M2.
- Every hook call exits 0. Stdout equals the adapter's `STDOUT` entry for that event when defined
  (Cursor `beforeSubmitPrompt`, Codex `Stop`, all Gemini events) and is empty otherwise.
- Empty stdin, the string `not json`, and `[]` all exit 0 with empty stdout.
- A hook call with `NT_SYNC` unset returns in under 2 seconds (interpreter start-up included) and story.md
  appears shortly after (detached narrator).
- Failure formats (unit tests): Claude `PostToolUseFailure` summary equals
  `Bash npm test: Error: Cannot find module 'express' (exit 1)`; Codex text `Exit code: 2` is an error and
  `Exit code: 0` is ok; Cursor stringified `{"exitCode": 1}` is an error; Gemini `tool_response.error` is an
  error; a Read whose output mentions "exit code 1" is ok.

**M4 Chunker** (`test_m4_chunker.py`): scenes for each fixture match table 9.3 exactly (phase, seqs, reasons, final).

**M5 Template end to end** (`test_m5_template_e2e.py`), with no `NT_LLM_*` env set:
- After replay, `story.md` exists and contains the 7 scene titles in order, every target path from 9.2, and the
  line `<sub>events #2-#3</sub>` (Claude Code).
- No scene text contains a causal word unless that scene has reasons.
- Running `narrate --all` again leaves `story.md` byte-identical and `scenes.jsonl` with the same line count.
- Same checks pass with `NT_LANG=en`.
- Replaying the same fixture twice into one project gives `## Turn 1` and `## Turn 2`, 7 scenes each.

**M6 LLM narrator and validator** (`test_m6_llm_validator.py`), using an injected fake `call` (no network):
- A faithful answer passes and is stored with source `"llm"`.
- An answer mentioning `src/Payment.tsx` (not in the scene) is rejected; with a second faithful answer the result
  is `"llm"`; with two bad answers the result is `"template_fallback"` and equals the template text.
- An answer with `because` on a scene without reasons is rejected.
- An answer formatted as a bullet list is rejected.
- A `call` that raises returns the template with source `"template_fallback"`.

**M7 Installer** (`test_m7_install.py`), in a temp project dir:
- `install` writes, per harness, the project config file below, with commands that use absolute paths:
  `"<sys.executable>" "<abs path to narrative_trace/launcher.py>" hook --harness <h> --event <E>`.
- The registered events equal the adapter's `EVENTS`. `uninstall` removes only our entries.
- `--dry-run` writes nothing and prints the JSON it would write.
- Running install twice does not duplicate entries. Pre-existing unrelated keys in the file are preserved.
  A `.bak` copy of the original file is created before modifying an existing file.

Config shapes to write:
- Claude Code `.claude/settings.json`:
  `{"hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": CMD}]}], "PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": CMD}]}], "PostToolUseFailure": [{"matcher": "*", "hooks": [...]}], "Stop": [{"hooks": [{"type": "command", "command": CMD}]}]}}`
- Codex `.codex/hooks.json`: same shape as Claude Code with events `UserPromptSubmit`, `PostToolUse`, `Stop`.
- Gemini CLI `.gemini/settings.json`:
  `{"hooks": {"BeforeAgent": [{"matcher": "*", "hooks": [{"name": "narrative-trace", "type": "command", "command": CMD}]}], "AfterTool": [...same...], "AfterAgent": [...same...]}}`
- Cursor `.cursor/hooks.json`:
  `{"version": 1, "hooks": {"beforeSubmitPrompt": [{"command": CMD}], "postToolUse": [{"command": CMD}], "postToolUseFailure": [{"command": CMD}], "afterAgentResponse": [{"command": CMD}], "stop": [{"command": CMD}]}}`

Each CMD carries its own `--event` value matching the key it sits under.

---

## 11. DEFINITION OF DONE

All of these must be true:
1. `python -m unittest discover -s tests -v` passes with zero failures and zero skips.
2. `python ntrace.py demo --harness claude_code --out /tmp/nt_demo` (any temp dir) produces a readable `story.md`.
3. `README.md` explains: what it is, install command per harness, `NT_LANG`, `NT_LLM_URL`/`NT_LLM_MODEL`/`NT_LLM_KEY`,
   where `story.md` lives, and the known limits below.
4. `REPORT.md` lists: test results (counts), every milestone and its status, and an ASSUMPTIONS section stating
   which payload shapes were checked only against documentation (not a live harness run), and that Codex and
   Gemini CLI require the user to trust new hooks before they run.
5. A pip install into a fresh virtualenv works, and the installed hook command, run through `sh -c` with a
   JSON payload on stdin, exits 0 and produces story.md.

Known limits to document (do not try to solve them):
- The agent's reasons are only available where the harness exposes the agent's text (full in Claude Code via the
  transcript; final message only in Codex and Gemini CLI; per response in Cursor).
- Live payload shapes can change between harness versions; check `errors.log` and the trace after first use.
- Tool names that Cursor and Codex use internally are not fully documented; unknown tools fall into the
  "other" phase instead of breaking anything.
- Hosted tools (for example Codex web search) do not fire tool hooks, so they never appear in the story.
