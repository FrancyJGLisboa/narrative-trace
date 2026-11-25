"""Regenerate narrative_trace/examples/* (the canonical checkout-button scenario)."""
import json
import os
import sys

base = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "narrative_trace", "examples")
PROMPT = "Fix the checkout button and run the tests"
WHY = ("The onClick calls handleCheckoutOld, which no longer exists. "
       "I will point it to handleCheckout.")
FINAL = "Fixed: the button now calls handleCheckout and all tests pass."
FAIL = "1 failed: Checkout.test.tsx expected label Pay"


def write(h, rows, transcript=None):
    d = os.path.join(base, h)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "payloads.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    if transcript:
        with open(os.path.join(d, "transcript.jsonl"), "w") as f:
            for r in transcript:
                f.write(json.dumps(r) + "\n")


def a(content):
    return {"type": "assistant", "message": {"role": "assistant", "content": content}}


def u(content):
    return {"type": "user", "message": {"role": "user", "content": content}}


def tu(name, inp):
    return [{"type": "tool_use", "id": "t", "name": name, "input": inp}]


TR = [{"type": "tool_result", "tool_use_id": "t", "content": "ok"}]
TRANSCRIPT = [
    u(PROMPT), a(tu("Read", {"file_path": "src/Checkout.tsx"})), u(TR),
    a(tu("Grep", {"pattern": "handleCheckout"})), u(TR), a([{"type": "text", "text": WHY}]),
    a(tu("Edit", {"file_path": "src/Checkout.tsx"})), u(TR),
    a(tu("Bash", {"command": "npm test"})), u(TR),
    a(tu("Edit", {"file_path": "src/Checkout.tsx"})), u(TR),
    a(tu("Bash", {"command": "npm test"})), u(TR), a([{"type": "text", "text": FINAL}]),
]
CC = {"session_id": "fx1", "cwd": "{CWD}", "transcript_path": "{TRANSCRIPT}"}


def cc(ev, upto, **kw):
    return {"event": ev, "payload": dict(CC, hook_event_name=ev, **kw), "transcript_upto": upto}


write("claude_code", [
    cc("UserPromptSubmit", 1, prompt=PROMPT),
    cc("PostToolUse", 3, tool_name="Read", tool_input={"file_path": "src/Checkout.tsx"},
       tool_response={"type": "text"}),
    cc("PostToolUse", 5, tool_name="Grep", tool_input={"pattern": "handleCheckout"},
       tool_response={"numFiles": 1}),
    cc("PostToolUse", 8, tool_name="Edit", tool_input={"file_path": "src/Checkout.tsx"},
       tool_response={"filePath": "src/Checkout.tsx"}),
    cc("PostToolUseFailure", 10, tool_name="Bash", tool_input={"command": "npm test"},
       error="Exit code 1\n" + FAIL, is_interrupt=False),
    cc("PostToolUse", 12, tool_name="Edit", tool_input={"file_path": "src/Checkout.tsx"},
       tool_response={"filePath": "src/Checkout.tsx"}),
    cc("PostToolUse", 14, tool_name="Bash", tool_input={"command": "npm test"},
       tool_response={"is_error": False, "stdout": "all passed"}),
    cc("Stop", 15, last_assistant_message=FINAL),
], TRANSCRIPT)


def plain(sid, start, post, stop, stop_key, steps):
    k = {"session_id": sid, "cwd": "{CWD}"}

    def p(ev, **kw):
        return {"event": ev, "payload": dict(k, hook_event_name=ev, **kw), "transcript_upto": None}

    rows = [p(start, prompt=PROMPT)]
    for name, inp, resp in steps:
        rows.append(p(post, tool_name=name, tool_input=inp, tool_response=resp))
    rows.append(p(stop, **{stop_key: FINAL}))
    return rows


# Codex: reads through the shell, edits with Edit/Write, shell output as text.
write("codex", plain("fx2", "UserPromptSubmit", "PostToolUse", "Stop", "last_assistant_message", [
    ("Bash", {"command": "cat src/Checkout.tsx"}, "Exit code: 0\nOutput:\nexport ..."),
    ("Bash", {"command": "rg handleCheckout"}, "Exit code: 0\nOutput:\nsrc/Checkout.tsx:88"),
    ("Edit", {"file_path": "src/Checkout.tsx"}, "Success"),
    ("Bash", {"command": "npm test"}, "Exit code: 1\nOutput:\n" + FAIL),
    ("Edit", {"file_path": "src/Checkout.tsx"}, "Success"),
    ("Bash", {"command": "npm test"}, "Exit code: 0\nOutput:\nall passed"),
]))

# Gemini CLI: tool_response = {llmContent, returnDisplay, error?}.
write("gemini_cli", plain("fx3", "BeforeAgent", "AfterTool", "AfterAgent", "prompt_response", [
    ("read_file", {"absolute_path": "src/Checkout.tsx"}, {"llmContent": "...", "returnDisplay": ""}),
    ("search_file_content", {"pattern": "handleCheckout"}, {"llmContent": "1 match", "returnDisplay": ""}),
    ("replace", {"file_path": "src/Checkout.tsx"}, {"llmContent": "ok", "returnDisplay": ""}),
    ("run_shell_command", {"command": "npm test"},
     {"llmContent": "Command: npm test\nDirectory: (root)\nOutput: " + FAIL + "\nExit Code: 1",
      "returnDisplay": FAIL}),
    ("replace", {"file_path": "src/Checkout.tsx"}, {"llmContent": "ok", "returnDisplay": ""}),
    ("run_shell_command", {"command": "npm test"},
     {"llmContent": "Command: npm test\nDirectory: (root)\nOutput: all passed\nExit Code: 0",
      "returnDisplay": "all passed"}),
]))

CU = {"conversation_id": "fx4", "workspace_roots": ["{CWD}"]}


def cu(ev, **kw):
    return {"event": ev, "payload": dict(CU, hook_event_name=ev, **kw), "transcript_upto": None}


write("cursor", [
    cu("beforeSubmitPrompt", prompt=PROMPT, attachments=[]),
    cu("postToolUse", tool_name="read_file", tool_input={"target_file": "src/Checkout.tsx"},
       tool_output='{"contents": "..."}'),
    cu("postToolUse", tool_name="grep", tool_input={"pattern": "handleCheckout"},
       tool_output='{"matches": 1}'),
    cu("afterAgentResponse", text=WHY),
    cu("postToolUse", tool_name="edit_file", tool_input={"target_file": "src/Checkout.tsx"},
       tool_output='{"ok": true}'),
    cu("postToolUseFailure", tool_name="run_terminal_cmd", tool_input={"command": "npm test"},
       error_message="Exit code 1\n" + FAIL, failure_type="error", is_interrupt=False),
    cu("postToolUse", tool_name="edit_file", tool_input={"target_file": "src/Checkout.tsx"},
       tool_output='{"ok": true}'),
    cu("postToolUse", tool_name="run_terminal_cmd", tool_input={"command": "npm test"},
       tool_output='{"exitCode": 0, "output": "all passed"}'),
    cu("afterAgentResponse", text=FINAL),
    cu("stop", status="completed", loop_count=0),
])
print("examples written to", base)
