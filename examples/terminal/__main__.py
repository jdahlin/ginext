"""`python -m examples.terminal` entry point - see app.py for the work."""

import sys

from .app import TerminalApp

raise SystemExit(TerminalApp().run(sys.argv))
