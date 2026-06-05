"""`python -m examples.terminal` entry point - see app.py for the work."""

import sys

from .app import App

raise SystemExit(App().run(sys.argv))
