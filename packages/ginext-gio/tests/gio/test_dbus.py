# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, see <http://www.gnu.org/licenses/>.

"""D-Bus overlay: bus_get awaitable, DBusProxy.__getattr__ method calls,
signal_subscribe and register_object context-manager tokens.

Tests that need a live bus run against the session-wide private dbus-daemon
(started in conftest, on a /tmp socket isolated from the developer's real bus).
Tests that only inspect return types or error paths run without a bus.
"""

from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from ginext import Gio, GLib
    from ginext.Gio import AsyncResult

import pytest

# Isolate from other xdist workers that also modify DBUS_SESSION_BUS_ADDRESS.
pytestmark = pytest.mark.xdist_group("dbus")

# Unix-fd passing (call_with_unix_fd_list) is POSIX-only; the methods are
# compiled out of GIO on Windows, so the overlay has nothing to wrap.
_skip_no_unix_fd = pytest.mark.skipif(
    sys.platform == "win32",
    reason="call_with_unix_fd_list is not available in GIO on Windows",
)


_ECHO_XML = """
<node>
  <interface name='com.example.Echo'>
    <method name='Echo'>
      <arg direction='in'  type='s' name='input'/>
      <arg direction='out' type='s' name='output'/>
    </method>
  </interface>
</node>
"""

_DBUS_BUS_NAME = "org.freedesktop.DBus"
_DBUS_OBJ_PATH = "/org/freedesktop/DBus"
_DBUS_IFACE = "org.freedesktop.DBus"


class Bus:
    def __init__(self, address: str) -> None:
        self._address = address

    def get_bus_address(self) -> str:
        return self._address


@pytest.fixture(scope="module")
def _dbus_daemon(dbus_session_bus: str) -> Generator[Bus]:
    """Hand out the address of the private session dbus-daemon.

    Backed by the session-scoped ``dbus_session_bus`` fixture (in the gio
    conftest), which starts one private bus for the whole session and kills it
    at exit — no per-test teardown wait. We deliberately do *not* use
    Gio.TestDBus here: its down() blocks ~30s on the cached session-bus
    GDBusConnection's weak-notify leak check.
    """

    yield Bus(dbus_session_bus)


@pytest.fixture
def session_bus(_dbus_daemon: Bus) -> Generator[Gio.DBusConnection]:
    """Per-test D-Bus connection to the private bus.

    Uses new_for_address instead of bus_get so each test gets a fresh,
    non-shared connection. bus_get caches its result: closing it in teardown
    leaves the cache pointing at the closed connection, so the next call
    returns that same closed connection and every subsequent test fails.

    close_sync deadlocks (its local context never sees the close ack because
    the connection's internal dispatch runs on the default context). The async
    close via asyncio.run pumps the default context correctly.

    Use _dbus_daemon.get_bus_address() rather than os.environ[...]: under
    xdist workers, g_setenv (called by TestDBus.up) may not be visible in
    Python's os.environ by the time this fixture runs.
    """
    import ginext
    from ginext import Gio, aio

    addr = _dbus_daemon.get_bus_address()
    flags = (
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
        | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION
    )

    def _start_connect(cb: Callable[[object, AsyncResult], None]) -> None:
        ginext.private.invoke(
            "Gio", "DBusConnection.new_for_address", addr, flags, None, None, cb
        )

    async def _connect() -> Gio.DBusConnection:
        return cast(
            "Gio.DBusConnection",
            await aio.AsyncOperation(
                _start_connect,
                lambda r: ginext.private.invoke(
                    "Gio", "DBusConnection.new_for_address_finish", r
                ),
            ),
        )

    conn = asyncio.run(_connect(), loop_factory=aio.EventLoop)
    yield conn

    def _start_close(cb: Callable[[object, AsyncResult], None]) -> None:
        ginext.private.invoke("Gio", "DBusConnection.close", conn, None, cb)

    async def _close() -> object:
        return await aio.AsyncOperation(
            _start_close,
            lambda r: ginext.private.invoke(
                "Gio", "DBusConnection.close_finish", conn, r
            ),
        )

    asyncio.run(_close(), loop_factory=aio.EventLoop)


@pytest.fixture
def dbus_proxy(session_bus: Gio.DBusConnection) -> Generator[Gio.DBusProxy]:
    """Per-test DBusProxy to org.freedesktop.DBus.

    Uses DBusProxy.new (explicit connection) instead of new_for_bus so it
    shares the test's non-cached session_bus connection rather than calling
    bus_get internally and hitting the shared-cache problem.
    """
    import ginext
    from ginext import Gio, aio

    def _start_make(cb: Callable[[object, AsyncResult], None]) -> None:
        ginext.private.invoke(
            "Gio",
            "DBusProxy.new",
            session_bus,
            Gio.DBusProxyFlags.NONE,
            None,
            _DBUS_BUS_NAME,
            _DBUS_OBJ_PATH,
            _DBUS_IFACE,
            None,
            cb,
        )

    async def _make() -> Gio.DBusProxy:
        return cast(
            "Gio.DBusProxy",
            await aio.AsyncOperation(
                _start_make,
                lambda r: Gio.DBusProxy.new_finish(r),  # r is AsyncResult at runtime
            ),
        )

    proxy = asyncio.run(_make(), loop_factory=aio.EventLoop)
    yield proxy


# ── DBusNodeInfo ──────────────────────────────────────────────────────────────


def test_node_info_parses_interface_name() -> None:
    from ginext import Gio

    info = Gio.DBusNodeInfo.new_for_xml(_ECHO_XML)
    assert info.interfaces[0].name == "com.example.Echo"


def test_node_info_parses_method_in_and_out_args() -> None:
    from ginext import Gio

    info = Gio.DBusNodeInfo.new_for_xml(_ECHO_XML)
    method = info.interfaces[0].methods[0]
    assert method.name == "Echo"
    assert method.in_args[0].name == "input"
    assert method.out_args[0].name == "output"


# ── Gio.bus_get overlay ────────────────────────────────────────────────────────


def test_bus_get_returns_awaitable() -> None:
    from ginext import Gio

    op = Gio.bus_get(Gio.BusType.SESSION)
    assert hasattr(op, "__await__")


def _assert_live_session_connection(conn: Gio.DBusConnection) -> None:
    # Behavioural check rather than isinstance(conn, ginext.Gio.DBusConnection):
    # when the gi.repository compat layer is also loaded (as it is in the test
    # session), the session-bus singleton may be wrapped by
    # gi.repository.Gio.DBusConnection — a *different* class object than
    # ginext.Gio.DBusConnection for the same GType, since the two namespaces do
    # not share wrapped classes. get_unique_name() is unique to a live
    # GDBusConnection, so it proves bus_get resolved to a real, open connection.
    unique_name = conn.get_unique_name()
    assert unique_name is not None
    assert unique_name.startswith(":")
    assert not conn.is_closed()


def test_bus_get_resolves_to_dbus_connection(session_bus: Gio.DBusConnection) -> None:
    from ginext import Gio, aio

    async def main() -> Gio.DBusConnection:
        return cast("Gio.DBusConnection", await Gio.bus_get(Gio.BusType.SESSION))

    conn = asyncio.run(main(), loop_factory=aio.EventLoop)
    _assert_live_session_connection(conn)


def test_bus_get_under_eventloop(session_bus: Gio.DBusConnection) -> None:
    from ginext import Gio, aio

    async def main() -> Gio.DBusConnection:
        return cast("Gio.DBusConnection", await Gio.bus_get(Gio.BusType.SESSION))

    conn = asyncio.run(main(), loop_factory=aio.EventLoop)
    _assert_live_session_connection(conn)


# ── DBusProxy.__getattr__ — Pythonic method calls ─────────────────────────────


def test_proxy_getattr_returns_callable(dbus_proxy: Gio.DBusProxy) -> None:
    call = dbus_proxy.ListNames
    assert callable(call)


def test_proxy_method_call_returns_awaitable(dbus_proxy: Gio.DBusProxy) -> None:
    op = dbus_proxy.ListNames()
    assert hasattr(op, "__await__")


def test_proxy_method_no_args_resolves_to_list(dbus_proxy: Gio.DBusProxy) -> None:
    """ListNames() → (as) → unboxed to a plain list (single-element tuple unboxed)."""
    from ginext import aio

    async def main() -> object:
        return await dbus_proxy.ListNames()

    result = asyncio.run(main(), loop_factory=aio.EventLoop)
    assert isinstance(result, list)
    assert _DBUS_BUS_NAME in result


def test_proxy_method_with_args_resolves(dbus_proxy: Gio.DBusProxy) -> None:
    """GetNameOwner('(s)', name) → (s) → unboxed to a string."""
    from ginext import aio

    async def main() -> object:
        return await dbus_proxy.GetNameOwner("(s)", _DBUS_BUS_NAME)

    owner = asyncio.run(main(), loop_factory=aio.EventLoop)
    assert isinstance(owner, str)
    assert owner == _DBUS_BUS_NAME


def test_proxy_method_raises_on_unknown_name(dbus_proxy: Gio.DBusProxy) -> None:
    from ginext import GLib, aio

    async def main() -> object:
        return await dbus_proxy.GetNameOwner("(s)", "com.does.not.exist")

    with pytest.raises(GLib.Error):
        asyncio.run(main(), loop_factory=aio.EventLoop)


def test_proxy_method_call_under_eventloop(dbus_proxy: Gio.DBusProxy) -> None:
    import asyncio

    from ginext import aio

    async def main() -> object:
        return await dbus_proxy.ListNames()

    result = asyncio.run(main(), loop_factory=aio.EventLoop)
    assert isinstance(result, list)


# ── DBusProxy.__getitem__ — cached properties ─────────────────────────────────


def test_proxy_getitem_missing_property_raises_key_error(
    dbus_proxy: Gio.DBusProxy,
) -> None:
    with pytest.raises(KeyError):
        _ = dbus_proxy["NoSuchProperty"]


# ── DBusConnection.signal_subscribe ──────────────────────────────────────────


def test_signal_subscribe_returns_token(session_bus: Gio.DBusConnection) -> None:

    token = session_bus.signal_subscribe(
        _DBUS_BUS_NAME,
        _DBUS_IFACE,
        "NameAcquired",
        _DBUS_OBJ_PATH,
        lambda *a: None,
    )
    assert token is not None
    token.cancel()


def test_signal_subscribe_token_is_context_manager(
    session_bus: Gio.DBusConnection,
) -> None:

    with session_bus.signal_subscribe(
        _DBUS_BUS_NAME,
        _DBUS_IFACE,
        "NameAcquired",
        _DBUS_OBJ_PATH,
        lambda *a: None,
    ) as token:
        assert token is not None


def test_signal_subscribe_unsubscribes_on_context_exit(
    session_bus: Gio.DBusConnection,
) -> None:
    """After exiting the context, the subscription id is gone from the bus."""

    with session_bus.signal_subscribe(
        _DBUS_BUS_NAME,
        _DBUS_IFACE,
        "NameAcquired",
        _DBUS_OBJ_PATH,
        lambda *a: None,
    ) as token:
        sub_id = token.subscription_id

    # Unsubscribing an already-unsubscribed id should be a no-op (not raise).
    session_bus.signal_unsubscribe(sub_id)


def test_signal_subscribe_receives_signal(session_bus: Gio.DBusConnection) -> None:
    """NameOwnerChanged arrives while the subscription is active.

    Trigger the signal by calling RequestName on the bus (which the daemon
    processes and then broadcasts NameOwnerChanged). Both the signal and the
    RequestName reply arrive in the same asyncio.run pump, so no second connection
    or asyncio.EventLoop is needed. sender=None avoids the well-known-name
    resolution round-trip that could let the signal race past before the pump
    starts.
    """
    from ginext import GLib, aio

    received: list[object] = []

    def on_signal(
        conn: Gio.DBusConnection,
        sender: str | None,
        path: str,
        iface: str,
        signal: str,
        params: GLib.Variant,
    ) -> None:
        received.append(params.unpack())

    with session_bus.signal_subscribe(
        None,
        _DBUS_IFACE,
        "NameOwnerChanged",
        _DBUS_OBJ_PATH,
        on_signal,
    ):

        def _start_request(cb: Callable[[object, AsyncResult], None]) -> None:
            session_bus.call(
                _DBUS_BUS_NAME,
                _DBUS_OBJ_PATH,
                _DBUS_IFACE,
                "RequestName",
                GLib.Variant("(su)", ("com.example.TestSignalReceive", 0)),
                None,
                0,
                -1,
                None,
                cb,
            )

        async def _request_name() -> object:
            return await aio.AsyncOperation(
                _start_request,
                lambda r: session_bus.call_finish(r),
            )

        asyncio.run(_request_name(), loop_factory=aio.EventLoop)

    assert len(received) > 0


# ── DBusConnection.register_object ───────────────────────────────────────────


def test_register_object_returns_token(session_bus: Gio.DBusConnection) -> None:
    from ginext import Gio

    info = Gio.DBusNodeInfo.new_for_xml(_ECHO_XML)
    token = session_bus.register_object(
        "/com/example/echo",
        info.interfaces[0],
        lambda *a: None,
    )
    assert token is not None
    token.cancel()


def test_register_object_token_is_context_manager(
    session_bus: Gio.DBusConnection,
) -> None:
    from ginext import Gio

    info = Gio.DBusNodeInfo.new_for_xml(_ECHO_XML)
    with session_bus.register_object(
        "/com/example/echo2",
        info.interfaces[0],
        lambda *a: None,
    ) as token:
        assert token is not None


def test_register_object_unregisters_on_context_exit(
    session_bus: Gio.DBusConnection,
) -> None:
    """Registering the same path again must succeed after context exit."""
    from ginext import Gio

    info = Gio.DBusNodeInfo.new_for_xml(_ECHO_XML)
    with session_bus.register_object(
        "/com/example/echo3",
        info.interfaces[0],
        lambda *a: None,
    ):
        pass

    # Same path must be re-registerable (unregister happened).
    token = session_bus.register_object(
        "/com/example/echo3",
        info.interfaces[0],
        lambda *a: None,
    )
    token.cancel()


def test_register_object_dispatches_method_call(
    session_bus: Gio.DBusConnection,
) -> None:
    """Registering an Echo method and calling it round-trips the string."""
    from ginext import Gio, GLib, aio

    info = Gio.DBusNodeInfo.new_for_xml(_ECHO_XML)

    def handle_method(
        conn: Gio.DBusConnection,
        sender: str | None,
        path: str,
        iface: str,
        method: str,
        params: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        if method == "Echo":
            (text,) = params.unpack()
            invocation.return_value(GLib.Variant("(s)", (text,)))

    def _start_echo(cb: Callable[[object, AsyncResult], None]) -> None:
        unique = session_bus.get_unique_name()
        session_bus.call(
            unique,
            "/com/example/echo4",
            "com.example.Echo",
            "Echo",
            GLib.Variant("(s)", ("ping",)),
            None,
            Gio.DBusCallFlags.NONE,
            -1,
            None,
            cb,
        )

    async def main() -> object:
        with session_bus.register_object(
            "/com/example/echo4",
            info.interfaces[0],
            handle_method,
        ):
            result = cast(
                "GLib.Variant",
                await aio.AsyncOperation(
                    _start_echo,
                    lambda r: session_bus.call_finish(r),
                ),
            )
        return result.unpack()

    assert asyncio.run(main(), loop_factory=aio.EventLoop) == ("ping",)


# ---------------------------------------------------------------------------
# call_with_unix_fd_list returns a NamedReturn (GVariant, GUnixFDList) so apps
# can read the OUT fd-list by name. The Gio overlay wraps the AsyncCallable's
# finish; these inspect the wiring and the NamedReturn shape (no bus needed).
# ---------------------------------------------------------------------------


def test_named_return_tuple_and_attr_access() -> None:
    """`NamedReturn` is a tuple subclass with attribute fallback."""
    from ginext.aio import NamedReturn

    r = NamedReturn(("ret", [1, 2, 3]), ("", "out_fd_list"))
    # Indexing + len + tuple unpacking — same as a plain tuple.
    assert r[0] == "ret"
    assert r[1] == [1, 2, 3]
    assert len(r) == 2
    a, b = r
    assert a == "ret"
    assert b == [1, 2, 3]
    # Attribute access for OUT param.
    assert r.out_fd_list == [1, 2, 3]
    # Still a tuple — isinstance + tuple operations work.
    assert isinstance(r, tuple)
    # Unknown attribute → AttributeError, not silent None.
    with pytest.raises(AttributeError):
        _ = r.does_not_exist


def test_named_return_attr_lookup_falls_back_to_first_match() -> None:
    """Multiple names — attribute access finds the matching index."""
    from ginext.aio import NamedReturn

    r = NamedReturn(("a", "b", "c"), ("", "out_x", "out_y"))
    assert r.out_x == "b"
    assert r.out_y == "c"


@_skip_no_unix_fd
def test_dbus_proxy_call_with_unix_fd_list_finish_is_overlay_wrapped() -> None:
    """`Gio.DBusProxy.call_with_unix_fd_list` is an AsyncCallable whose finish
    is wrapped to deliver a NamedReturn."""
    from ginext import Gio
    from ginext.aio import AsyncCallable

    ac = Gio.DBusProxy.call_with_unix_fd_list
    assert isinstance(ac, AsyncCallable)
    assert ac._finish_fn.__name__ == "_wrapped_finish"


@_skip_no_unix_fd
def test_dbus_connection_call_with_unix_fd_list_finish_is_overlay_wrapped() -> None:
    """Same wrap on DBusConnection (the lower-level path used by code that does
    not go through a proxy)."""
    from ginext import Gio
    from ginext.aio import AsyncCallable

    ac = Gio.DBusConnection.call_with_unix_fd_list
    assert isinstance(ac, AsyncCallable)
    assert ac._finish_fn.__name__ == "_wrapped_finish"
