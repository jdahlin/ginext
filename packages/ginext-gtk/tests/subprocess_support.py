# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import json
import pathlib
import subprocess
import sys


def run_subprocess_probe(
    module_file: str,
    probe_name: str,
    *,
    timeout: int = 5,
    **kwargs: object,
) -> object:
    module_path = pathlib.Path(module_file).resolve()
    package_root = module_path.parents[2]
    module_name = ".".join(module_path.relative_to(package_root).with_suffix("").parts)
    runner = pathlib.Path(__file__).with_name("subprocess_runner.py")
    proc = subprocess.run(
        [
            sys.executable,
            str(runner),
            str(package_root),
            module_name,
            probe_name,
            json.dumps(kwargs),
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(proc.stdout.strip())
