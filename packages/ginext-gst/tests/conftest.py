# SPDX-License-Identifier: LGPL-2.1-or-later

# Importing conftest_shared runs its module-level _restore_asan_preload(), which
# puts DYLD_INSERT_LIBRARIES back into os.environ so the many inline
# subprocess.run() spawns in the gst plugin tests inherit the asan runtime on
# macOS. The gst suite has no other conftest that pulls conftest_shared in.
import conftest_shared  # noqa: F401
