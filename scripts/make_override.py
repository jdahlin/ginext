#!/usr/bin/env python3
"""Build a .override ZIP (uncompressed) from a list of Python source files.

Usage: make_override.py OUTPUT.override SOURCE1.py [SOURCE2.py ...]

Each source file is stored in the ZIP under its basename.  The ZIP uses
STORED (no compression) so goi can use zero-copy mmap slices at runtime.
"""

import sys
import os
import zipfile

output = sys.argv[1]
inputs = sys.argv[2:]

with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as zf:
    for path in inputs:
        zf.write(path, os.path.basename(path))
