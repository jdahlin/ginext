# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import importlib
import json
import os
import pathlib
import sys


def main() -> None:
    package_root = pathlib.Path(sys.argv[1]).resolve()
    module_name = sys.argv[2]
    probe_name = sys.argv[3]
    kwargs = json.loads(sys.argv[4])

    sys.path.insert(0, str(package_root))

    # On Windows the _gobject extension's DLL dependencies (glib/gobject/gio/...)
    # are found via os.add_dll_directory, not PATH. The parent test process
    # exports the directories in GINEXT_WIN_DLL_DIRS; re-register them here before
    # importing ginext so the probe subprocess can load the extension.
    if sys.platform == "win32":
        for _dir in os.environ.get("GINEXT_WIN_DLL_DIRS", "").split(os.pathsep):
            if _dir and os.path.isdir(_dir):
                os.add_dll_directory(_dir)

    module = importlib.import_module(module_name)
    probe = getattr(module, probe_name)
    sys.stdout.write(json.dumps(probe(**kwargs)))
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
