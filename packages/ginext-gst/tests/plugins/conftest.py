from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TESTS_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

from conftest_shared import (
    configure_subprocess_marker,
    maybe_run_test_in_subprocess,
    rebuild_editable,
    setup_package_paths,
    suppress_editable_rebuild,
)


_NINJA_CMD, _BUILD_PATH = suppress_editable_rebuild()
setup_package_paths(ROOT)


def pytest_sessionstart(session: pytest.Session) -> None:
    rebuild_editable(_NINJA_CMD, _BUILD_PATH)


def pytest_configure(config: pytest.Config) -> None:
    configure_subprocess_marker(config)


def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    return maybe_run_test_in_subprocess(pyfuncitem)


@pytest.fixture(scope="session")
def Gst():
    import ginext

    ns = ginext.Gst
    ns.init(None)
    return ns
