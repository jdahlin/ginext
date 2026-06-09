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

"""`do_<vfunc>` vtable-override tests on Python GObject subclasses.

Modeled on pygobject's tests/test_subclass.py shape. Each test
declares a fresh GObject subclass with `type_name=` (so goi's
__init_subclass__ registers a new GType) and a `do_X` method matching
an introspected vfunc. The vfunc is patched into the parent's class
struct at class-build time; the assertion is that the Python method
fires when the C call site dispatches through the vtable.

Showtime's `Application.do_activate` is the motivating real-world case.
"""

from __future__ import annotations

import itertools
import sys
from typing import Any, Callable

import pytest

from ginext import Gio as _Gio
from ginext.tests.typelib.support import assert_gobject_class_mro


_subclass_seq = itertools.count()


def _unique_name(prefix: str) -> str:
    return f"{prefix}_{next(_subclass_seq)}"


def test_application_mro_uses_live_gobject_object(Gio: Any) -> None:
    assert_gobject_class_mro(Gio.Application)


def test_do_activate_overrides_default(Gio: Any) -> None:
    """The motivating case: subclass of Gio.Application with
    `do_activate` runs the override instead of GLib's default impl
    (which would emit the
       "Your application does not implement g_application_activate()"
    warning)."""
    fired = []

    class MyApp(_Gio.Application, type_name=_unique_name("VfuncActivate")):

        def do_activate(self) -> None:
            fired.append("activate")

    app = MyApp(application_id="org.goi.test.vfunc.activate", flags=0)
    app.run([])
    assert fired == ["activate"]


def test_do_activate_receives_self(Gio: Any) -> None:
    """The C → Python trampoline marshals the GApplication* arg to a
    wrapped instance — the override sees `self` correctly."""
    captured = []

    class MyApp(_Gio.Application, type_name=_unique_name("VfuncActivateSelf")):

        def do_activate(self) -> None:
            captured.append(self)

    app = MyApp(application_id="org.goi.test.vfunc.self", flags=0)
    app.run([])
    assert len(captured) == 1
    assert captured[0] is app


def test_do_shutdown_overrides_via_vtable(Gio: Any) -> None:
    """`shutdown` is dispatched via signal emission like `activate`,
    and is called on application teardown. Confirms vtable patches
    work for more than just activate."""
    fired = []

    class MyApp(_Gio.Application, type_name=_unique_name("VfuncShutdown")):

        def do_activate(self) -> None:
            fired.append("activate")

        def do_shutdown(self) -> None:
            fired.append("shutdown")
            Gio.Application.do_shutdown(self)

    app = MyApp(application_id="org.goi.test.vfunc.shutdown", flags=0)
    app.run([])
    assert "activate" in fired
    assert "shutdown" in fired


def test_subclass_without_do_activate_still_warns(Gio: Any) -> None:
    """Sanity: a subclass with no `do_*` overrides falls through to
    the parent's default vfuncs. We don't assert the warning fires
    (it's a glib runtime g_warning, not a Python warning) — just that
    nothing crashes and the subclass otherwise behaves normally."""

    class MyApp(_Gio.Application, type_name=_unique_name("VfuncNoOverride")):
        pass

    app = MyApp(application_id="org.goi.test.vfunc.none", flags=0)
    # We can't trivially run() without activate without GLib whining,
    # so just verify the class exists and instantiation works.
    assert type(app).__name__ == "MyApp"


def test_unrelated_do_attr_is_not_treated_as_vfunc(Gio: Any) -> None:
    """A `do_xxx` method that doesn't match any introspected vfunc
    on the parent's class is just a regular method — no closure is
    installed and the method is reachable as a normal attribute."""

    class MyApp(_Gio.Application, type_name=_unique_name("VfuncBogus")):

        def do_not_a_real_vfunc(self) -> Any:
            return 42

        def do_activate(self) -> None:
            pass

    app = MyApp(application_id="org.goi.test.vfunc.bogus", flags=0)
    assert app.do_not_a_real_vfunc() == 42


# --- Chain-up: Parent.do_X(self) ----------------------------------------


def test_gir_class_exposes_do_X_for_chain_up(Gio: Any) -> None:
    """GIR-built classes get `do_<vfunc>` attributes auto-installed
    so subclasses can chain up via `Parent.do_X(self)`. Mirrors
    pygobject's _setup_native_vfuncs. The attribute is a callable
    wrapper holding the vfunc info; calling it invokes the parent's
    vfunc on `self` via gi_vfunc_info_invoke."""
    assert hasattr(Gio.Application, "do_startup")
    assert hasattr(Gio.Application, "do_activate")
    # Sanity-check the repr names the vfunc.
    assert "startup" in repr(Gio.Application.do_startup)


def test_override_chains_up_to_parent_vfunc(Gio: Any) -> None:
    """Showtime's pattern: subclass's do_startup calls
    Parent.do_startup(self) to keep the parent's default-handler
    logic in place. The chain-up dispatches through the parent's
    class struct, so it doesn't recurse into our own override."""
    seq = []

    class MyApp(_Gio.Application, type_name=_unique_name("VfuncChainUp")):

        def do_startup(self) -> None:
            seq.append("override")
            Gio.Application.do_startup(self)
            seq.append("after chain-up")

        def do_activate(self) -> None:
            seq.append("activate")

    app = MyApp(application_id="org.goi.test.vfunc.chainup", flags=0)
    app.run([])
    assert seq == ["override", "after chain-up", "activate"]


def test_no_subclass_chain_up_still_works(Gio: Any) -> None:
    """Direct `Parent.do_X(self)` on a non-overriding subclass should
    invoke the parent's default-handler path with no weird recursion."""

    class MyApp(_Gio.Application, type_name=_unique_name("VfuncNoOverrideChain")):

        def do_activate(self) -> None:
            # Call parent's activate directly — parent's default impl
            # is a g_warning, but it doesn't crash and shouldn't
            # recurse into us.
            Gio.Application.do_activate(self)

    app = MyApp(application_id="org.goi.test.vfunc.nooverride", flags=0)
    app.run([])  # warning expected; no crash, no recursion


def test_super_do_startup_chains_up(Gio: Any) -> None:
    """Subclass `do_startup` can call `super().do_startup()` without
    recursing into itself or requiring explicit `self`."""
    seq: list[str] = []

    class App(_Gio.Application, type_name=_unique_name("SuperChainUpApp")):

        def do_startup(self) -> None:
            seq.append("before")
            super().do_startup()
            seq.append("after")

    app = App(
        application_id="org.goi.SuperChainUp",
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )
    app.register(None)
    assert seq == ["before", "after"]


@pytest.mark.xfail(
    sys.platform == "win32",
    reason="GApplication.run ignores the passed argv on Windows (parses the real "
    "process command line via GetCommandLineW), so the injected options "
    "never reach handle_local_options",
    strict=True,
)
def test_chain_up_marshals_boxed_vfunc_arguments(Gio: Any, GLib: Any) -> None:
    """Parent.do_X(self, boxed) accepts boxed wrappers during chain-up.

    This covers the core vfunc wrapper path for non-GObject arguments:
    GLib.VariantDict is a boxed wrapper, not a GObject, so the chain-up
    descriptor must unwrap it before calling gi_vfunc_info_invoke.
    """
    seen: list[str] = []

    class App(
        _Gio.Application, type_name=_unique_name("VfuncHandleLocalOptionsChainUp")
    ):

        def do_handle_local_options(self, options: object) -> int:
            assert isinstance(options, GLib.VariantDict)
            seen.append(options.lookup_value("string", None).unpack())
            result = Gio.Application.do_handle_local_options(self, options)
            seen.append(f"result:{result}")
            return 0

    app = App(flags=Gio.ApplicationFlags.NON_UNIQUE)
    app.add_main_option(
        long_name="string",
        short_name=ord("s"),
        flags=0,
        arg=GLib.OptionArg.STRING,
        description="some string",
        arg_description=None,
    )

    assert app.run(["app", "-s", "test string"]) == 0
    assert seen == ["test string", "result:-1"]


def test_input_stream_close_async_vfunc_receives_wrapped_callback(
    Gio: Any, GLib: Any, unique_type_name: Any
) -> None:
    """`do_close_async` should receive a callable callback wrapper, not None.

    This is a headless repro for the generic C->Python vfunc callback gap:
    Gio.InputStream.close_async dispatches into our Python vfunc override,
    and the `GAsyncReadyCallback` parameter should already be wrapped as a
    Python callable with its closure/user_data bound.
    """
    seen: dict[str, Any] = {}

    class CloseAsyncStream(
        _Gio.MemoryInputStream,
        type_name=unique_type_name("CloseAsyncVfunc"),
    ):
        def do_close_async(
            self,
            io_priority: int,
            cancellable: _Gio.Cancellable | None = None,
            callback: Callable[[_Gio.InputStream | None, _Gio.AsyncResult], None]
            | None = None,
            *extra: object,
        ) -> None:
            seen["io_priority"] = io_priority
            seen["cancellable"] = cancellable
            seen["callback"] = callback
            seen["user_data"] = extra[0] if extra else None

            assert callable(callback)
            callback(self, _Gio.Task.new(self, cancellable, None))

        def do_close_finish(self, result: _Gio.AsyncResult) -> bool:
            seen["finish_result"] = result
            return True

    obj = CloseAsyncStream()

    def on_done(source: _Gio.InputStream | None, result: _Gio.AsyncResult) -> None:
        seen["done_source"] = source
        seen["done_result"] = result
        seen["finish_return"] = obj.close_finish(result)

    obj.close_async(GLib.PRIORITY_DEFAULT, None, on_done)

    assert seen["callback"] is not None
    assert seen["user_data"] is None
    assert seen["done_source"] is obj
    assert seen["done_result"] is seen["finish_result"]
    assert seen["finish_return"] is True


def test_ambiguous_gst_vfunc_short_name_is_rejected() -> None:
    import ginext

    if not hasattr(ginext, "GstBase"):
        pytest.skip("GstBase not available")

    GstBase = ginext.GstBase

    with pytest.raises(TypeError, match="do_query"):

        class AmbiguousTransform(  # type: ignore[call-arg]
            GstBase.BaseTransform,
            type_name=_unique_name("AmbiguousTransform"),
        ):
            def do_query(self, direction: object, query: object) -> bool:
                del direction, query
                return False


def test_explicit_gst_base_qualified_vfunc_name_is_accepted() -> None:
    import ginext

    if not hasattr(ginext, "GstBase"):
        pytest.skip("GstBase not available")

    GstBase = ginext.GstBase

    class ExplicitTransform(  # type: ignore[call-arg]
        GstBase.BaseTransform,
        type_name=_unique_name("ExplicitTransform"),
    ):
        def do_base_transform_query(self, direction: object, query: object) -> bool:
            return False

    assert ExplicitTransform.gimeta.gtype != 0
