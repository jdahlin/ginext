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

from __future__ import annotations

import pytest


def test_default_construction() -> None:
    from ginext import Gio

    c = Gio.Cancellable()
    assert isinstance(c, Gio.Cancellable)


def test_construction_produces_distinct_instances() -> None:
    from ginext import Gio

    a = Gio.Cancellable()
    b = Gio.Cancellable()
    assert a is not b


def test_constructed_instance_is_gobject_object() -> None:
    from ginext import Gio, GObject

    c = Gio.Cancellable()
    assert isinstance(c, GObject.Object)


def test_positional_args_to_generic_construct_raise() -> None:
    from ginext import Gio

    with pytest.raises(TypeError):
        Gio.Cancellable("positional")  # type: ignore[call-arg]  # testing runtime rejection


def test_unknown_kwarg_raises_with_clear_error() -> None:
    from ginext import Gio

    with pytest.raises((TypeError, ValueError)) as excinfo:
        Gio.Cancellable(no_such_property=True)
    msg = str(excinfo.value)
    assert "no_such_property" in msg or "no-such-property" in msg


def test_does_not_expose_new() -> None:
    from ginext import Gio

    assert "new" not in {n for n in dir(Gio.Cancellable) if not n.startswith("_")}


def test_is_cancelled_returns_true() -> None:
    from ginext import Gio

    c = Gio.Cancellable()
    c.cancel()
    assert c.is_cancelled() is True


def test_is_cancelled_returns_false() -> None:
    from ginext import Gio

    c = Gio.Cancellable()
    assert c.is_cancelled() is False


def test_is_cancelled_returns_python_bool_not_int() -> None:
    from ginext import Gio

    result = Gio.Cancellable().is_cancelled()
    assert isinstance(result, bool)


def test_cancel_returns_none() -> None:
    from ginext import Gio

    result = Gio.Cancellable().cancel()  # type: ignore[func-returns-value]  # testing that cancel() returns None
    assert result is None


def test_cancel_has_side_effect() -> None:
    from ginext import Gio

    c = Gio.Cancellable()
    c.cancel()
    assert c.is_cancelled() is True


def test_reset_clears_cancelled_state() -> None:
    from ginext import Gio

    c = Gio.Cancellable()
    c.cancel()
    c.reset()
    assert c.is_cancelled() is False


def test_get_fd_returns_int_scalar() -> None:
    from ginext import Gio

    fd = Gio.Cancellable().get_fd()
    assert isinstance(fd, int)
    assert fd >= -1


def test_class_call_with_explicit_self() -> None:
    from ginext import Gio

    c = Gio.Cancellable()
    Gio.Cancellable.cancel(c)
    assert c.is_cancelled() is True


def test_calling_instance_method_without_self_raises() -> None:
    from ginext import Gio

    with pytest.raises(TypeError):
        Gio.Cancellable.cancel()  # type: ignore[call-arg]  # testing runtime rejection: missing self


def test_get_current_without_active_scope() -> None:
    from ginext import Gio

    if not hasattr(Gio.Cancellable, "get_current"):
        pytest.skip("Gio.Cancellable.get_current not present")

    result = Gio.Cancellable.get_current()
    assert result is None or isinstance(result, Gio.Cancellable)


def test_get_current_preserves_wrapper_identity() -> None:
    from ginext import Gio

    cancellable = Gio.Cancellable()
    cancellable.push_current()
    try:
        assert Gio.Cancellable.get_current() is cancellable
    finally:
        cancellable.pop_current()


def test_ref_lifecycle_methods_are_hidden() -> None:
    from ginext import Gio

    item = Gio.Cancellable()
    assert "ref" not in dir(Gio.Cancellable)
    assert "unref" not in dir(Gio.Cancellable)
    assert not hasattr(item, "ref")
    assert not hasattr(item, "unref")


def test_qdata_weakref_does_not_keep_wrapper_alive() -> None:
    import gc
    import weakref

    from ginext import Gio

    obj = Gio.Cancellable()
    ref = weakref.ref(obj)
    del obj
    gc.collect()

    assert ref() is None


def test_subclass_construct_returns_instance() -> None:
    from ginext import Gio

    class MyC(Gio.Cancellable):
        pass

    obj = MyC()
    assert isinstance(obj, MyC)
    assert isinstance(obj, Gio.Cancellable)


def test_subclass_init_called_in_addition_to_construct() -> None:
    from ginext import Gio

    saw = {}

    class MyC(Gio.Cancellable):
        def __init__(self) -> None:
            super().__init__()
            saw["was_cancelled"] = self.is_cancelled()

    MyC()
    assert saw["was_cancelled"] is False


def test_subclass_new_does_not_construct_c_instance() -> None:
    from ginext import Gio

    class MyC(Gio.Cancellable):
        def __init__(self) -> None:
            pass

    inst = MyC()
    assert inst.is_bound() is False


def test_subclass_keeps_python_subclass_identity() -> None:
    from ginext import Gio

    class MyC(Gio.Cancellable):
        pass

    obj = MyC()
    assert type(obj) is MyC
    assert isinstance(obj, Gio.Cancellable)


def test_not_floating_after_construct() -> None:
    from ginext import Gio

    c = Gio.Cancellable()
    assert c.is_floating() is False


def test_descriptor_get_returns_callable() -> None:
    from ginext import Gio

    desc = Gio.Cancellable.cancel
    inst = Gio.Cancellable()
    bound = desc.__get__(inst, Gio.Cancellable)
    bound()
    assert inst.is_cancelled() is True


def test_descriptor_get_on_class_returns_callable() -> None:
    from ginext import Gio

    desc = Gio.Cancellable.cancel
    assert callable(desc.__get__(None, Gio.Cancellable))


def test_descriptor_bound_form_is_callable() -> None:
    from ginext import Gio

    assert callable(Gio.Cancellable().cancel)


def test_descriptor_is_shared_across_instances() -> None:
    from ginext import Gio

    a = Gio.Cancellable()
    b = Gio.Cancellable()
    a.cancel
    b.cancel
    assert type(a).__dict__["cancel"] is type(b).__dict__["cancel"]


def test_descriptor_qualified_name_mentions_class_and_method() -> None:
    from ginext import Gio

    desc = Gio.Cancellable.cancel
    qn = getattr(desc, "__qualname__", None) or repr(desc)
    assert "Cancellable" in qn
    assert "cancel" in qn


def test_methods_appear_in_dir() -> None:
    from ginext import Gio

    listed = dir(Gio.Cancellable)
    assert "cancel" in listed
    assert "is_cancelled" in listed


# -- context-manager cancel scope ---------------------------------------------


def test_context_manager_returns_self() -> None:
    from ginext import Gio

    c = Gio.Cancellable()
    with c as entered:
        assert entered is c


def test_context_manager_cancels_on_exit() -> None:
    from ginext import Gio

    with Gio.Cancellable() as c:
        assert c.is_cancelled() is False
    assert c.is_cancelled() is True


def test_context_manager_cancels_on_exception() -> None:
    from ginext import Gio

    captured = None
    with pytest.raises(ValueError, match="boom"), Gio.Cancellable() as c:
        captured = c
        raise ValueError("boom")
    assert captured.is_cancelled() is True  # type: ignore[union-attr]


def test_context_manager_is_current_inside_scope() -> None:
    from ginext import Gio

    with Gio.Cancellable() as c:
        assert Gio.Cancellable.get_current() is c
    assert Gio.Cancellable.get_current() is None


def test_nested_context_managers_restore_outer_scope() -> None:
    from ginext import Gio

    with Gio.Cancellable() as outer:
        assert Gio.Cancellable.get_current() is outer
        with Gio.Cancellable() as inner:
            assert Gio.Cancellable.get_current() is inner
        assert Gio.Cancellable.get_current() is outer
    assert Gio.Cancellable.get_current() is None
