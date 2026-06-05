"""`python -m examples.pyedit` entry point — see app.py for the work."""

import sys

from examples.pyedit.app import App

raise SystemExit(App().run(sys.argv))
