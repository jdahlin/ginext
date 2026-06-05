# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import os

import pytest


@pytest.mark.subprocess(timeout=10)
def test_subprocess_marker_runs_test_body_in_child_process() -> None:
    assert os.environ.get("PYGIR_PYTEST_SUBPROCESS") == "1"
