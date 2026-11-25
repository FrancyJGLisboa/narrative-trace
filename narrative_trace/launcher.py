"""Stable entry point for hook commands: works from a git clone or a pip install."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from narrative_trace.cli import main  # noqa: E402

main()
