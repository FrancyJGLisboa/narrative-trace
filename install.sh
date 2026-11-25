#!/bin/sh
# Narrative Trace one-line installer (macOS / Linux / WSL / Git Bash).
#   curl -fsSL https://raw.githubusercontent.com/FrancyJGLisboa/narrative-trace/main/install.sh | sh
# Options (pass after "sh -s --"):  --harness claude_code|codex|gemini_cli|cursor|all|auto
#                                   --scope user|project   (default: user = every project)
set -eu
REPO="https://github.com/FrancyJGLisboa/narrative-trace"
DEST="${NT_INSTALL_DIR:-$HOME/.narrative-trace}"

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
[ -n "$PY" ] || { echo "narrative-trace: Python 3.9+ is required." >&2; exit 1; }

if command -v git >/dev/null 2>&1; then
  if [ -d "$DEST/.git" ]; then git -C "$DEST" pull -q --ff-only; else git clone -q --depth 1 "$REPO" "$DEST"; fi
else
  mkdir -p "$DEST"
  curl -fsSL "$REPO/archive/refs/heads/main.tar.gz" | tar -xz -C "$DEST" --strip-components=1
fi

HARNESS="auto"; SCOPE="user"
while [ $# -gt 0 ]; do
  case "$1" in
    --harness) HARNESS="$2"; shift 2;;
    --scope) SCOPE="$2"; shift 2;;
    *) shift;;
  esac
done
"$PY" "$DEST/ntrace.py" install --harness "$HARNESS" --scope "$SCOPE" --project "$(pwd)"
echo "Done. Uninstall: $PY $DEST/ntrace.py uninstall --harness all --scope $SCOPE"
