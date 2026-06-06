from __future__ import annotations

import pathlib
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

ROOT = pathlib.Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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


# Known win32 gap: ginext does not yet treat GstCaps/GstBuffer/GstSample/etc. as
# GstMiniObject subtypes on Windows (g_type_is_a(GST_TYPE_CAPS, MINI_OBJECT) is
# False), so writability / mini-object semantics fail. xfail (non-strict) on
# win32 until that subtyping is implemented.
_WIN32_MINIOBJECT_XFAIL = frozenset(
    {
        "test_buffer_list.py::TestBufferList::test_make_writable_returns_buffer_list",
        "test_buffer_list.py::TestBufferList::test_copy_result_not_writable",
        "test_mini_object.py::TestMiniObjectSemantics::test_caps_is_writable",
        "test_mini_object.py::TestMiniObjectSemantics::test_event_is_writable",
        "test_mini_object.py::TestMiniObjectSemantics::test_message_is_writable",
        "test_mini_object.py::TestMiniObjectSemantics::test_query_is_writable",
        "test_mini_object.py::TestMiniObjectSemantics::test_tag_list_is_writable",
        "test_sample.py::TestSample::test_set_buffer",
        "test_sample.py::TestSample::test_set_caps",
        "test_sample.py::TestSample::test_set_segment",
        "test_sample.py::TestSample::test_make_writable_returns_sample",
    }
)


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if sys.platform != "win32":
        return
    mark = pytest.mark.xfail(
        reason="win32: GstMiniObject subtyping not yet supported", strict=False
    )
    for item in items:
        nid = item.nodeid.replace("\\", "/")
        if any(nid.endswith(suffix) for suffix in _WIN32_MINIOBJECT_XFAIL):
            item.add_marker(mark)


def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    return maybe_run_test_in_subprocess(pyfuncitem)


@pytest.fixture(name="Gst")
def fixture_gst() -> ModuleType:
    import ginext

    ns = ginext.Gst
    ns.init(None)
    return ns
