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
    module = importlib.import_module(module_name)
    probe = getattr(module, probe_name)
    sys.stdout.write(json.dumps(probe(**kwargs)))
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
