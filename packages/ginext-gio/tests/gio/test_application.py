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

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

from __future__ import annotations

import sys
from typing import Any

import pytest

# GApplication.run ignores its argv argument on Windows and parses the real
# process command line via GetCommandLineW, so tests that inject argv (options,
# command-line, open-with-files) cannot observe their input there.
_xfail_win32_argv = pytest.mark.xfail(
    sys.platform == "win32",
    reason="GApplication.run ignores the passed argv on Windows (GetCommandLineW)",
    strict=True,
)


APPLICATION_VFUNCS_WITH_ACTIVE_DISPATCH_TESTS = {
    "activate",
    "command_line",
    "dbus_register",
    "handle_local_options",
    "local_command_line",
    "open",
    "shutdown",
    "startup",
}

# Vfuncs that only fire across two cooperating application instances (a
# primary plus a remote invocation) or on bus-name contention. In-process
# dispatch tests cannot trigger them — the second instance would collide on
# the shared bus connection's exported object path — so asserting them needs a
# multi-process remote-activation harness. The inventory test confirms they
# exist; dispatch coverage is deferred.
APPLICATION_VFUNCS_DEFERRED = {
    "add_platform_data",
    "after_emit",
    "before_emit",
    "name_lost",
}


def test_application_vfunc_inventory_is_covered() -> None:
    from ginext import Gio

    data = Gio.Application.gimeta.gi_info.object_info()
    vfunc_names = {info.get_name() for info in data["vfuncs"]}

    # Every vfunc we cover (actively or deferred) must be a real Application
    # vfunc. Extra vfuncs we don't care about (e.g. the legacy run/quit
    # mainloop vtable entries) are ignored rather than enumerated.
    assert vfunc_names >= (
        APPLICATION_VFUNCS_WITH_ACTIVE_DISPATCH_TESTS | APPLICATION_VFUNCS_DEFERRED
    )
    assert (
        set(Gio.Application.gimeta.vfunc_infos)
        >= APPLICATION_VFUNCS_WITH_ACTIVE_DISPATCH_TESTS
    )


def test_construct_with_scalar_property() -> None:
    pytest.importorskip("ginext")
    from ginext import Gio

    app = Gio.Application(application_id="org.example.GinextTest")
    assert app.get_application_id() == "org.example.GinextTest"


def test_construct_with_multiple_scalar_properties() -> None:
    pytest.importorskip("ginext")
    from ginext import Gio

    app = Gio.Application(
        application_id="org.example.GinextTest",
        inactivity_timeout=42,
    )
    assert app.get_application_id() == "org.example.GinextTest"
    assert app.get_inactivity_timeout() == 42


def test_invalid_application_id_type_raises() -> None:
    pytest.importorskip("ginext")
    from ginext import Gio

    with pytest.raises(TypeError):
        Gio.Application(application_id=123)


def test_unknown_property_raises() -> None:
    pytest.importorskip("ginext")
    from ginext import Gio

    with pytest.raises((TypeError, ValueError)):
        Gio.Application(this_is_not_a_real_property=1)


def test_underscored_kwarg_maps_to_dashed_property() -> None:
    pytest.importorskip("ginext")
    from ginext import Gio

    app = Gio.Application(inactivity_timeout=42)
    assert app.get_inactivity_timeout() == 42


def test_dashed_kwarg_also_accepted_for_compatibility() -> None:
    pytest.importorskip("ginext")
    from ginext import Gio

    try:
        app = Gio.Application(**{"inactivity-timeout": 42})
    except TypeError:
        pytest.skip("dashed kwargs not accepted (policy choice)")
    else:
        assert app.get_inactivity_timeout() == 42


def test_unknown_after_normalization_mentions_property_name() -> None:
    pytest.importorskip("ginext")
    from ginext import Gio

    with pytest.raises((TypeError, ValueError)) as excinfo:
        Gio.Application(no_such_property=1)
    msg = str(excinfo.value)
    assert "no_such_property" in msg or "no-such-property" in msg


@_xfail_win32_argv
def test_add_main_option() -> None:
    from ginext import GLib, Gio

    stored_options = []

    def on_handle_local_options(_app: object, options: object) -> int:
        stored_options.append(options)
        return 0

    app = Gio.Application()
    app.add_main_option(
        long_name="string",
        short_name=ord("s"),
        flags=0,
        arg=GLib.OptionArg.STRING,
        description="some string",
        arg_description=None,
    )
    app.handle_local_options.connect(on_handle_local_options)

    assert app.run(["app", "-s", "test string"]) == 0
    assert len(stored_options) == 1
    assert stored_options[0].contains("string") is True  # type: ignore[attr-defined]
    assert stored_options[0].lookup_value("string", None).unpack() == "test string"  # type: ignore[attr-defined]


def test_lifecycle_vfuncs_dispatch_and_can_chain_up() -> None:
    from ginext import Gio

    class App(Gio.Application):
        def __init__(self) -> None:
            super().__init__(
                application_id="org.example.GinextLifecycle",
                flags=Gio.ApplicationFlags.NON_UNIQUE,
            )
            self.events: list[str] = []

        def do_startup(self) -> None:
            Gio.Application.do_startup(self)
            self.events.append("startup")

        def do_activate(self) -> None:
            self.events.append("activate")
            self.quit()

        def do_shutdown(self) -> None:
            self.events.append("shutdown")
            Gio.Application.do_shutdown(self)

    app = App()

    assert app.run(["app"]) == 0
    assert app.events == ["startup", "activate", "shutdown"]


def test_do_activate_receives_self() -> None:
    from ginext import Gio

    captured = []

    class App(Gio.Application):
        def __init__(self) -> None:
            super().__init__(
                application_id="org.example.GinextVfuncSelf",
                flags=Gio.ApplicationFlags.NON_UNIQUE,
            )

        def do_activate(self) -> None:
            captured.append(self)
            self.quit()

    app = App()

    assert app.run(["app"]) == 0
    assert captured == [app]


def test_unrelated_do_attr_is_not_treated_as_vfunc() -> None:
    from ginext import Gio

    class App(Gio.Application):
        def do_not_a_real_vfunc(self) -> int:
            return 42

        def do_activate(self) -> None:
            self.quit()

    app = App(
        application_id="org.example.GinextBogusVfunc",
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )

    assert app.do_not_a_real_vfunc() == 42


def test_no_subclass_chain_up_still_works() -> None:
    from ginext import Gio

    class App(Gio.Application):
        def __init__(self) -> None:
            super().__init__(
                application_id="org.example.GinextNoOverrideChain",
                flags=Gio.ApplicationFlags.NON_UNIQUE,
            )

        def do_activate(self) -> None:
            Gio.Application.do_activate(self)
            self.quit()

    app = App()

    assert app.run(["app"]) == 0


def test_super_do_startup_chains_up() -> None:
    from ginext import Gio

    seq: list[str] = []

    class App(Gio.Application):
        def __init__(self) -> None:
            super().__init__(
                application_id="org.example.GinextSuperChainUp",
                flags=Gio.ApplicationFlags.NON_UNIQUE,
            )

        def do_startup(self) -> None:
            seq.append("before")
            super().do_startup()
            seq.append("after")

    app = App()

    app.register(None)
    assert seq == ["before", "after"]


@_xfail_win32_argv
def test_open_vfunc_includes_file_count_arg_used_by_apps() -> None:
    from ginext import Gio

    class App(Gio.Application):
        opened = None

        def __init__(self) -> None:
            super().__init__(
                application_id="org.example.GinextOpen",
                flags=(
                    Gio.ApplicationFlags.HANDLES_OPEN | Gio.ApplicationFlags.NON_UNIQUE
                ),
            )

        def do_open(self, files: list[Gio.File], hint: str) -> None:
            self.opened = [file.get_path() for file in files], len(files), hint
            self.quit()

    app = App()

    assert app.run(["app", "/tmp/ginext-open-test"]) == 0
    assert app.opened == (["/tmp/ginext-open-test"], 1, "")


@_xfail_win32_argv
def test_handle_local_options_vfunc() -> None:
    from ginext import GLib, Gio

    class App(Gio.Application):
        options = None

        def do_handle_local_options(self, options: object) -> int:
            self.options = options
            return 0

    app = App()
    app.add_main_option(
        long_name="string",
        short_name=ord("s"),
        flags=0,
        arg=GLib.OptionArg.STRING,
        description="some string",
        arg_description=None,
    )

    assert app.run(["app", "-s", "test string"]) == 0
    assert app.options is not None
    assert app.options.contains("string") is True  # type: ignore[attr-defined]


# These run an application against the private session bus from the
# dbus_session_bus fixture (self-contained; no Gio.TestDBus, whose down()
# blocks ~30s). A unique application_id keeps each test isolated; the app
# releases the name immediately on quit.
def test_dbus_register_vfunc_used_by_apps(dbus_session_bus: str) -> None:
    from ginext import Gio

    class App(Gio.Application):
        registrations: list[Any]

        def __init__(self) -> None:
            super().__init__(application_id="org.example.GinextDBusRegister")
            self.registrations = []

        def do_dbus_register(self, connection: object, object_path: str) -> bool:
            self.registrations.append((connection, object_path))
            return True

        def do_activate(self) -> None:
            self.quit()

    app = App()
    assert app.run(["app"]) == 0
    assert len(app.registrations) == 1
    connection, object_path = app.registrations[0]
    assert isinstance(connection, Gio.DBusConnection)
    assert object_path == "/org/example/GinextDBusRegister"


def test_dbus_unregister_vfunc_used_by_apps(dbus_session_bus: str) -> None:
    from ginext import Gio

    class App(Gio.Application):
        events: list[str]

        def __init__(self) -> None:
            super().__init__(application_id="org.example.GinextDBusUnregister")
            self.events = []

        def do_dbus_register(self, connection: object, object_path: str) -> bool:
            self.events.append("register")
            return True

        def do_dbus_unregister(self, connection: object, object_path: str) -> None:
            self.events.append("unregister")

        def do_activate(self) -> None:
            self.quit()

    app = App()
    assert app.run(["app"]) == 0
    # register fires when the app acquires the bus name; unregister fires when
    # the registration is torn down as the app shuts down.
    assert app.events == ["register", "unregister"]


@_xfail_win32_argv
def test_command_line() -> None:
    from ginext import Gio

    class App(Gio.Application):
        args = None

        def __init__(self) -> None:
            super().__init__(flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)

        def do_command_line(self, cmdline: object) -> int:
            self.args = cmdline.get_arguments()  # type: ignore[attr-defined]
            return 42

    app = App()

    assert app.run(["spam", "eggs"]) == 42
    assert app.args == ["spam", "eggs"]


@_xfail_win32_argv
def test_local_command_line() -> None:
    from ginext import Gio

    class App(Gio.Application):
        local_args = None

        def __init__(self) -> None:
            super().__init__(flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)

        def do_local_command_line(self, args: list[str]) -> tuple[bool, list[str], int]:
            self.local_args = args[:]
            args.remove("eggs")
            return True, args, 42

    app = App()

    assert app.run(["spam", "eggs"]) == 42
    assert app.local_args == ["spam", "eggs"]


@_xfail_win32_argv
def test_local_and_remote_command_line() -> None:
    from ginext import Gio

    class App(Gio.Application):
        args = None
        local_args = None

        def __init__(self) -> None:
            super().__init__(flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)

        def do_command_line(self, cmdline: object) -> int:
            self.args = cmdline.get_arguments()  # type: ignore[attr-defined]
            return 42

        def do_local_command_line(self, args: list[str]) -> tuple[bool, list[str], int]:
            self.local_args = args[:]
            args.remove("eggs")
            return False, args, 0

    app = App()

    assert app.run(["spam", "eggs"]) == 42
    assert app.args == ["spam"]
    assert app.local_args == ["spam", "eggs"]


@pytest.mark.parametrize("vfunc_name", sorted(APPLICATION_VFUNCS_DEFERRED))
@pytest.mark.xfail(
    reason=(
        "fires only across two application instances (primary + remote "
        "activation) or on bus-name contention; needs a multi-process harness"
    ),
    run=False,
    strict=False,
)
def test_deferred_application_vfunc_dispatch(vfunc_name: str) -> None:
    assert vfunc_name
