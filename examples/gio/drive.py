#!/usr/bin/env python3
"""List connected drives via Gio.VolumeMonitor with ginext.

Run via:
    PYTHONPATH=build/cpython-3.14t/src \\
      .venv-cpython-3.14t/bin/python3 examples/gio/drive.py

The enumeration methods take no arguments. Output depends on the machine and
may be empty in a container.
"""

from __future__ import annotations

from ginext import Gio


def main() -> int:
    monitor = Gio.VolumeMonitor.get()
    drives = monitor.get_connected_drives()

    if not drives:
        print("no connected drives")
        return 0

    for drive in drives:
        print(f"{drive.get_name()}")
        print(f"  removable:   {drive.is_removable()}")
        print(f"  has media:   {drive.has_media()}")
        print(f"  can eject:   {drive.can_eject()}")
        for volume in drive.get_volumes():
            print(f"  volume:      {volume.get_name()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
