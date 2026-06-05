#!/usr/bin/env python3
"""List volumes and mounts via Gio.VolumeMonitor with ginext.

Run via:
    PYTHONPATH=build/cpython-3.14t/src \\
      .venv-cpython-3.14t/bin/python3 examples/gio/volume.py

The enumeration methods take no arguments. Output depends on the machine and
may be empty in a container.
"""

from __future__ import annotations

from ginext import Gio


def main() -> int:
    monitor = Gio.VolumeMonitor.get()

    volumes = monitor.get_volumes()
    print(f"volumes ({len(volumes)}):")
    for volume in volumes:
        mount = volume.get_mount()
        where = mount.get_root().get_path() if mount is not None else "(not mounted)"
        print(f"  {volume.get_name()} -> {where}")

    mounts = monitor.get_mounts()
    print(f"\nmounts ({len(mounts)}):")
    for mount in mounts:
        print(f"  {mount.get_name()} at {mount.get_root().get_uri()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
