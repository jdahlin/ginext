from __future__ import annotations

import itertools
import sys

import pytest

from conftest_shared import configure_subprocess_marker, maybe_run_test_in_subprocess

# Shared private-session-D-Bus fixture (repo root is on sys.path via the
# `pythonpath` pytest setting), reused across the gio and gi-compat suites.
from dbus_fixtures import dbus_session_bus as dbus_session_bus


_type_name_counter = itertools.count()


def pytest_configure(config: pytest.Config) -> None:
    configure_subprocess_marker(config)

    # ginext's GLib-backed asyncio EventLoop is not yet ported to Windows
    # (g_source_add_unix_fd is POSIX-only). Rather than fail every async test,
    # turn any attempt to construct the loop into a skip, so the rest of the
    # gio suite still runs. See _aioloop.EventLoop for the underlying guard.
    if sys.platform == "win32":
        from ginext import aio

        def _skip_eventloop(*args: object, **kwargs: object) -> object:
            pytest.skip(
                "ginext asyncio EventLoop is not supported on Windows "
                "(g_source_add_unix_fd is POSIX-only)"
            )

        aio.EventLoop = _skip_eventloop  # type: ignore[attr-defined]

        # The skip fires from the loop factory, after the test's coroutine has
        # already been created, so it is never awaited. The resulting
        # "coroutine never awaited" RuntimeWarning is emitted during GC and
        # surfaces via pytest's unraisable-exception hook (which bypasses the
        # message-level filter), so ignore that category here too. Both are
        # pure artifacts of skipping async tests on Windows.
        config.addinivalue_line(
            "filterwarnings",
            r"ignore:coroutine '.*' was never awaited:RuntimeWarning",
        )
        config.addinivalue_line(
            "filterwarnings",
            "ignore::pytest.PytestUnraisableExceptionWarning",
        )


def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    return maybe_run_test_in_subprocess(pyfuncitem)


@pytest.fixture(scope="session")
def GObject():
    from ginext.gobject import gobjectclass as mod

    return mod.GObject


@pytest.fixture(scope="session")
def GLib():
    from ginext import GLib

    return GLib


@pytest.fixture(scope="session")
def Gio():
    from ginext import Gio

    return Gio


@pytest.fixture
def unique_type_name():
    def _next(prefix: str = "GinextPropTest") -> str:
        return f"{prefix}{next(_type_name_counter):04d}"

    return _next
