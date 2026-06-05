"""`python -m examples.web_browser` entry point — see app.py for the work."""

import sys

from examples.web_browser.app import App

raise SystemExit(App().run(sys.argv))
