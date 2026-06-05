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

import gc
import weakref
from typing import TYPE_CHECKING, Protocol, cast

import pytest

from .support import assert_gobject_class_mro, open_namespace_for_test

if TYPE_CHECKING:
    from ginext.namespace import Namespace


class _HasInstanceMethod(Protocol):
    def instance_method(self) -> object: ...


@pytest.fixture
def t(call_mode: str) -> Namespace:
    return open_namespace_for_test(call_mode, "Regress", "1.0")


@pytest.fixture
def test_obj(t: Namespace) -> object:
    return t.TestObj()


def _drain_callback_async(t: Namespace) -> None:
    while t.test_callback_thaw_async() != 0:
        pass


def _drain_callback_notifications(t: Namespace) -> None:
    while t.test_callback_thaw_notifications() != 0:
        pass


def test_test_obj_mro_uses_live_gobject_object(t: Namespace) -> None:
    assert_gobject_class_mro(t.TestObj)


def test_boolean_true(t: Namespace) -> None:
    assert t.test_boolean(True) is True


def test_boolean_false(t: Namespace) -> None:
    assert t.test_boolean(False) is False


def test_boolean_true_true(t: Namespace) -> None:
    assert t.test_boolean_true(True) is True


def test_boolean_false_false(t: Namespace) -> None:
    assert t.test_boolean_false(False) is False


def test_int8_positive(t: Namespace) -> None:
    assert t.test_int8(100) == 100


def test_int8_negative(t: Namespace) -> None:
    assert t.test_int8(-100) == -100


def test_uint8(t: Namespace) -> None:
    assert t.test_uint8(200) == 200


def test_int16_positive(t: Namespace) -> None:
    assert t.test_int16(30_000) == 30_000


def test_int16_negative(t: Namespace) -> None:
    assert t.test_int16(-30_000) == -30_000


def test_uint16(t: Namespace) -> None:
    assert t.test_uint16(60_000) == 60_000


def test_int32_positive(t: Namespace) -> None:
    assert t.test_int32(1_000_000) == 1_000_000


def test_int32_negative(t: Namespace) -> None:
    assert t.test_int32(-1_000_000) == -1_000_000


def test_uint32(t: Namespace) -> None:
    assert t.test_uint32(3_000_000_000) == 3_000_000_000


def test_int64_positive(t: Namespace) -> None:
    assert t.test_int64(1 << 40) == 1 << 40


def test_int64_negative(t: Namespace) -> None:
    assert t.test_int64(-(1 << 40)) == -(1 << 40)


def test_uint64(t: Namespace) -> None:
    assert t.test_uint64(1 << 50) == 1 << 50


def test_int_positive(t: Namespace) -> None:
    assert t.test_int(42) == 42


def test_int_negative(t: Namespace) -> None:
    assert t.test_int(-1) == -1


def test_uint(t: Namespace) -> None:
    assert t.test_uint(42) == 42


def test_short(t: Namespace) -> None:
    assert t.test_short(-5) == -5


def test_ushort(t: Namespace) -> None:
    assert t.test_ushort(65535) == 65535


def test_long(t: Namespace) -> None:
    assert t.test_long(1 << 30) == 1 << 30


def test_ulong(t: Namespace) -> None:
    assert t.test_ulong(1 << 30) == 1 << 30


def test_size(t: Namespace) -> None:
    assert t.test_size(8192) == 8192


def test_ssize(t: Namespace) -> None:
    assert t.test_ssize(-8192) == -8192


def test_gtype(t: Namespace) -> None:
    assert t.test_gtype(24) == 24


def test_unichar(t: Namespace) -> None:
    # ginext marshals `gunichar` (and the test_regress identity-return)
    # as a length-1 `str`, matching PyGObject - predicates like
    # GtkTextCharPredicate then compare against char literals
    # naturally (`ch == "a"`).
    assert t.test_unichar(ord("A")) == "A"


def test_timet(t: Namespace) -> None:
    assert t.test_timet(1234) == 1234


def test_offt(t: Namespace) -> None:
    assert t.test_offt(1234) == 1234


def test_utf8_const_return(t: Namespace) -> None:
    assert t.test_utf8_const_return() == "const ♥ utf8"


def test_utf8_nonconst_return(t: Namespace) -> None:
    assert t.test_utf8_nonconst_return() == "nonconst ♥ utf8"


def test_return_allow_none(t: Namespace) -> None:
    assert t.test_return_allow_none() is None


def test_return_nullable(t: Namespace) -> None:
    assert t.test_return_nullable() is None


def test_utf8_const_in(t: Namespace) -> None:
    assert t.test_utf8_const_in("const ♥ utf8") is None


def test_utf8_out(t: Namespace) -> None:
    assert t.test_utf8_out() == "nonconst ♥ utf8"


def test_utf8_inout(t: Namespace) -> None:
    assert t.test_utf8_inout("const ♥ utf8") == "nonconst ♥ utf8"


def test_utf8_null_in(t: Namespace) -> None:
    assert t.test_utf8_null_in(None) is None


def test_utf8_null_out(t: Namespace) -> None:
    assert t.test_utf8_null_out() is None


def test_utf8_out_out(t: Namespace) -> None:
    assert t.test_utf8_out_out() == ("first", "second")


def test_utf8_out_nonconst_return(t: Namespace) -> None:
    assert t.test_utf8_out_nonconst_return() == ("first", "second")


def test_float(t: Namespace) -> None:
    assert t.test_float(2.5) == pytest.approx(2.5)


def test_double(t: Namespace) -> None:
    assert t.test_double(3.14159) == pytest.approx(3.14159)


def test_enum_param(t: Namespace) -> None:
    assert t.test_enum_param(t.TestEnum.VALUE1) == "value1"
    assert t.test_enum_param(t.TestEnum.VALUE2) == "value2"


def test_unsigned_enum_param(t: Namespace) -> None:
    assert t.test_unsigned_enum_param(t.TestEnumUnsigned.VALUE1) == "value1"
    assert t.test_unsigned_enum_param(t.TestEnumUnsigned.VALUE2) == "value2"


def test_instance_method(test_obj: object) -> None:
    value = cast("_HasInstanceMethod", test_obj).instance_method()
    assert isinstance(value, int)


def test_set_bare_with_object(test_obj: object, t: Namespace) -> None:
    if not hasattr(test_obj, "set_bare"):
        pytest.skip("Regress.TestObj.set_bare not exposed in this typelib version")
    other = t.TestObj()
    test_obj.set_bare(other)
    if hasattr(test_obj, "get_bare"):
        got = test_obj.get_bare()
        assert got is other or repr(got) == repr(other)


def test_set_bare_rejects_wrong_type(test_obj: object) -> None:
    if not hasattr(test_obj, "set_bare"):
        pytest.skip("Regress.TestObj.set_bare not exposed in this typelib version")
    with pytest.raises(TypeError):
        test_obj.set_bare("not a gobject")


def test_python_subclass_construction(t: Namespace) -> None:
    class MyObj(t.TestObj):  # type: ignore[misc, name-defined]  # runtime-loaded class, irreducible
        pass

    inst = MyObj()
    assert isinstance(inst, MyObj)
    assert isinstance(inst, t.TestObj)
    # `gimeta.gtype` is ginext's "built by us" marker - GObjectBase
    # itself isn't part of the public API.
    assert type(inst).gimeta.gtype
    assert isinstance(inst.instance_method(), int)
    # The wrapper should hold the only ref to the underlying GObject.

    assert inst.ref_count() == 1
    assert inst.__grefcount__ == 1


def test_grefcount_property_matches_object_ref_count(t: Namespace) -> None:

    inst = t.TestObj()
    assert inst.__grefcount__ == inst.ref_count()


def test_aliased_caller_alloc(t: Namespace) -> None:
    t.aliased_caller_alloc()


def test_annotation_attribute_func(t: Namespace) -> None:
    obj = t.AnnotationObject()
    assert t.annotation_attribute_func(obj, "data") == 42


def test_annotation_custom_destroy(t: Namespace) -> None:
    t.annotation_custom_destroy(lambda: None)


def test_annotation_custom_destroy_cleanup(t: Namespace) -> None:
    t.annotation_custom_destroy_cleanup()


def test_annotation_get_source_file(t: Namespace) -> None:
    t.annotation_get_source_file()


def test_annotation_init(t: Namespace) -> None:
    t.annotation_init(["program", "arg1"])


def test_annotation_invalid_regress_annotation(t: Namespace) -> None:
    t.annotation_invalid_regress_annotation(42)


def test_annotation_ptr_array(t: Namespace) -> None:
    t.annotation_ptr_array([])


def test_annotation_return_array(t: Namespace) -> None:
    t.annotation_return_array()


def test_annotation_return_filename(t: Namespace) -> None:
    t.annotation_return_filename()


def test_annotation_set_source_file(t: Namespace) -> None:
    t.annotation_set_source_file("source.c")


def test_annotation_space_after_comment_bug631690(t: Namespace) -> None:
    t.annotation_space_after_comment_bug631690()


def test_annotation_string_array_length(t: Namespace) -> None:
    t.annotation_string_array_length(["a", "b", "c"])


def test_annotation_string_zero_terminated(t: Namespace) -> None:
    t.annotation_string_zero_terminated()


def test_annotation_string_zero_terminated_out(t: Namespace) -> None:
    t.annotation_string_zero_terminated_out([])


def test_annotation_test_parsing_bug630862(t: Namespace) -> None:
    t.annotation_test_parsing_bug630862()


def test_annotation_transfer_floating(t: Namespace) -> None:
    assert t.annotation_transfer_floating(None) is None


def test_annotation_versioned(t: Namespace) -> None:
    t.annotation_versioned()


def test_atest_error_quark(t: Namespace) -> None:
    t.atest_error_quark()


def test_foo_async_ready_callback(t: Namespace) -> None:
    """C body missing from foo.c; the call is satisfied by a synthetic
    overlay (see src/overlays/Regress-1.0.toml) that skips GI dispatch
    and yields None."""
    t.foo_async_ready_callback()


def test_foo_destroy_notify_callback(t: Namespace) -> None:
    """C body missing from foo.c; satisfied by a synthetic overlay with
    two declared params that drive the public Python arity."""
    t.foo_destroy_notify_callback(lambda data: 0, None)


def test_foo_enum_method(t: Namespace) -> None:
    assert t.foo_enum_method(t.FooEnumType.ALPHA) == 0


def test_foo_enum_type_method(t: Namespace) -> None:
    assert t.foo_enum_type_method(t.FooEnumType.ALPHA) == 1
    assert t.foo_enum_type_method(t.FooEnumType.BETA) == 2
    assert t.foo_enum_type_method(t.FooEnumType.DELTA) == 0


def test_foo_enum_type_returnv(t: Namespace) -> None:
    assert t.foo_enum_type_returnv(0) == t.FooEnumType.BETA
    assert t.foo_enum_type_returnv(1) == t.FooEnumType.DELTA
    assert t.foo_enum_type_returnv(2) == t.FooEnumType.ALPHA


def test_foo_error_quark(t: Namespace) -> None:
    t.foo_error_quark()


def test_foo_init(t: Namespace) -> None:
    t.foo_init()


def test_foo_init_argv(t: Namespace) -> None:
    assert t.foo_init_argv(["program", "arg1"]) == 0x1138


def test_foo_init_argv_address(t: Namespace) -> None:
    t.foo_init_argv_address(["program", "arg1"])


def test_foo_interface_static_method(t: Namespace) -> None:
    t.foo_interface_static_method(42)


def test_foo_method_external_references(t: Namespace) -> None:
    t.foo_method_external_references(None, 0, 0, None)


def test_foo_not_a_constructor_new(t: Namespace) -> None:
    t.foo_not_a_constructor_new()


def test_foo_test_array(t: Namespace) -> None:
    t.foo_test_array()


def test_foo_test_const_char_param(t: Namespace) -> None:
    """C body missing; synthetic overlay accepts the arg and yields None."""
    t.foo_test_const_char_param("hello")


def test_foo_test_const_char_retval(t: Namespace) -> None:
    """C body missing; synthetic overlay yields a literal "stub" string
    so the isinstance(str) assertion holds."""
    assert isinstance(t.foo_test_const_char_retval(), str)


def test_foo_test_const_struct_param(t: Namespace) -> None:
    """C body missing; synthetic overlay accepts the arg and yields None."""
    t.foo_test_const_struct_param(None)


def test_foo_test_const_struct_retval(t: Namespace) -> None:
    """C body missing; synthetic overlay default-passthrough yields None,
    which matches the assertion."""
    assert t.foo_test_const_struct_retval() is None


def test_foo_test_string_array(t: Namespace) -> None:
    t.foo_test_string_array(["a", "b", "c"])


def test_foo_test_string_array_with_g(t: Namespace) -> None:
    t.foo_test_string_array_with_g(["a", "b", "c"])


def test_foo_test_unsigned(t: Namespace) -> None:
    t.foo_test_unsigned(42)


def test_foo_test_unsigned_type(t: Namespace) -> None:
    """`regress_foo_test_unsigned_type` is declared in foo.h but missing
    from foo.c. The compiled overlay in src/overlays/Regress-1.0.toml
    redirects this call to the implemented same-shape sibling
    `regress_foo_test_unsigned`."""
    t.foo_test_unsigned_type(42)


def test_func_obj_null_in(t: Namespace) -> None:
    t.func_obj_null_in(None)


def test_func_obj_nullable_in(t: Namespace) -> None:
    t.func_obj_nullable_in(t.TestObj())


def test_get_variant(t: Namespace) -> None:
    v = t.get_variant()
    assert v is not None


def test_global_get_flags_out(t: Namespace) -> None:
    flags = t.global_get_flags_out()
    assert flags == t.TestFlags.FLAG1 | t.TestFlags.FLAG3


def test_has_parameter_named_attrs(t: Namespace) -> None:
    t.has_parameter_named_attrs(0, None)


def test_introspectable_via_alias(t: Namespace) -> None:
    t.introspectable_via_alias([])


def test_set_abort_on_error(t: Namespace) -> None:
    """C body missing from regress.c; synthetic overlay accepts the arg
    and yields None."""
    t.set_abort_on_error(False)


def test_test_abc_error_quark(t: Namespace) -> None:
    t.test_abc_error_quark()


def test_test_array_callback(t: Namespace) -> None:
    t.test_array_callback(lambda one, two: 0)


def test_test_array_fixed_boxed_none_out(t: Namespace) -> None:
    t.test_array_fixed_boxed_none_out()


def test_test_array_fixed_out_objects(t: Namespace) -> None:
    t.test_array_fixed_out_objects()


def test_test_array_fixed_size_int_in(t: Namespace) -> None:
    assert t.test_array_fixed_size_int_in([1, 2, -10, 5, 3]) == 1


def test_test_array_fixed_size_int_in_rejects_wrong_length(t: Namespace) -> None:
    with pytest.raises(ValueError):
        t.test_array_fixed_size_int_in([1, 2, 3, 4])
    with pytest.raises(ValueError):
        t.test_array_fixed_size_int_in([1, 2, 3, 4, 5, 6])


def test_test_array_fixed_size_int_out(t: Namespace) -> None:
    assert list(t.test_array_fixed_size_int_out()) == [0, 1, 2, 3, 4]


def test_test_array_fixed_size_int_return(t: Namespace) -> None:
    assert list(t.test_array_fixed_size_int_return()) == [0, 1, 2, 3, 4]


def test_test_array_gint16_in(t: Namespace) -> None:
    assert t.test_array_gint16_in([-1, 0, 1, 2]) == 2


def test_test_array_gint32_in(t: Namespace) -> None:
    assert t.test_array_gint32_in([-1, 0, 1, 2]) == 2


def test_test_array_gint64_in(t: Namespace) -> None:
    assert t.test_array_gint64_in([-1, 0, 1, 2]) == 2


def test_test_array_gint8_in(t: Namespace) -> None:
    assert t.test_array_gint8_in([-1, 0, 1, 2]) == 2


def test_test_array_gtype_in(t: Namespace) -> None:
    # GType values: 16=GBoolean, 24=GInt - just exercise the call path
    result = t.test_array_gtype_in([16, 24])
    assert isinstance(result, str)
    assert result.startswith("[") and result.endswith("]")


def test_test_array_inout_callback(t: Namespace) -> None:
    """Callback `(int **ints, int *length)` with `length="1"` annotation.
    The closure trampoline pairs the array+length on the way in (so
    Python sees a single list) and writes the returned list back as a
    freshly-allocated C array, updating the length partner. The C body
    asserts the callback strips the first element each time."""
    t.test_array_inout_callback(lambda arr: arr[1:])


def test_test_array_int_full_out(t: Namespace) -> None:
    assert list(t.test_array_int_full_out()) == [0, 1, 2, 3, 4]


def test_test_array_int_in(t: Namespace) -> None:
    assert t.test_array_int_in([1, 2, 3]) == 6


def test_test_array_int_inout(t: Namespace) -> None:
    assert list(t.test_array_int_inout([1, 2, 3])) == [3, 4]


def test_test_array_int_none_out(t: Namespace) -> None:
    assert list(t.test_array_int_none_out()) == [1, 2, 3, 4, 5]


def test_test_array_int_null_in(t: Namespace) -> None:
    t.test_array_int_null_in(None)


def test_test_array_int_null_out(t: Namespace) -> None:
    result = t.test_array_int_null_out()
    assert result is None or list(result) == []


def test_test_array_int_out(t: Namespace) -> None:
    assert list(t.test_array_int_out()) == [0, 1, 2, 3, 4]


# test_array_of_fundamental_objects_in/out moved to tests/test_fundamental.py.


def test_test_array_of_non_utf8_strings(t: Namespace) -> None:
    t.test_array_of_non_utf8_strings()


def test_test_array_static_in_int(t: Namespace) -> None:
    t.test_array_static_in_int([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])


def test_test_array_struct_in_full(t: Namespace) -> None:
    s1 = t.TestStructA()
    s1.some_int = 201
    s2 = t.TestStructA()
    s2.some_int = 202
    t.test_array_struct_in_full([s1, s2])


def test_test_array_struct_in_none(t: Namespace) -> None:
    s1 = t.TestStructA()
    s1.some_int = 301
    s2 = t.TestStructA()
    s2.some_int = 302
    s3 = t.TestStructA()
    s3.some_int = 303
    t.test_array_struct_in_none([s1, s2, s3])


def test_test_array_struct_out(t: Namespace) -> None:
    t.test_array_struct_out()


def test_test_array_struct_out_caller_alloc(t: Namespace) -> None:
    """Caller-allocates flat C-array `(out caller-allocates) + (out length)`
    where the C ABI takes the length BY VALUE — a known GIR annotation
    mismatch. The plan layer rewrites the length's direction to IN
    (matching C's actual ABI) and the bind layer fills the length slot
    from the array's allocated element count, avoiding the gigabyte-
    memset that the literal GIR direction would cause."""
    result = t.test_array_struct_out_caller_alloc()
    assert isinstance(result, list)


def test_test_array_struct_out_container(t: Namespace) -> None:
    t.test_array_struct_out_container()


def test_test_array_struct_out_full_fixed(t: Namespace) -> None:
    t.test_array_struct_out_full_fixed()


def test_test_array_struct_out_none(t: Namespace) -> None:
    t.test_array_struct_out_none()


def test_test_async_ready_callback(t: Namespace) -> None:
    t.test_async_ready_callback()


def test_test_boxeds_not_a_method(t: Namespace) -> None:
    t.test_boxeds_not_a_method(None)


def test_test_boxeds_not_a_static(t: Namespace) -> None:
    t.test_boxeds_not_a_static()


def test_test_callback(t: Namespace) -> None:
    assert t.test_callback(lambda: 42) == 42
    assert t.test_callback(None) == 0


def test_test_callback_async(t: Namespace) -> None:
    _drain_callback_async(t)
    t.test_callback_async(lambda ud: 42, None)
    assert t.test_callback_thaw_async() == 42


def test_scope_async_callback_user_data_released_after_thaw(t: Namespace) -> None:
    _drain_callback_async(t)

    class Sentinel:
        pass

    sentinel = Sentinel()
    sentinel_ref = weakref.ref(sentinel)
    seen = []

    def callback(user_data: object) -> object:
        seen.append(user_data is sentinel_ref())
        return 42

    t.test_callback_async(callback, sentinel)
    del sentinel

    assert t.test_callback_thaw_async() == 42
    gc.collect()
    gc.collect()

    assert seen == [True]
    assert sentinel_ref() is None


def test_scope_async_callback_itself_released_after_thaw(t: Namespace) -> None:
    _drain_callback_async(t)

    class Callback:
        def __call__(self, user_data: object) -> object:
            return 42

    callback = Callback()
    callback_ref = weakref.ref(callback)

    t.test_callback_async(callback, None)
    del callback

    assert t.test_callback_thaw_async() == 42
    gc.collect()
    gc.collect()

    assert callback_ref() is None


def test_test_callback_destroy_notify(t: Namespace) -> None:
    _drain_callback_notifications(t)
    assert (
        t.test_callback_destroy_notify(lambda *args: 42, None, lambda *args: None) == 42
    )
    assert t.test_callback_thaw_notifications() == 42


def test_scope_notified_callback_user_data_released_by_destroy_notify(
    t: Namespace,
) -> None:
    _drain_callback_notifications(t)

    class Sentinel:
        pass

    sentinel = Sentinel()
    sentinel_ref = weakref.ref(sentinel)

    assert t.test_callback_destroy_notify(lambda user_data: 42, sentinel) == 42
    assert t.test_callback_thaw_notifications() == 42

    del sentinel
    gc.collect()
    gc.collect()

    assert sentinel_ref() is None


def test_test_callback_destroy_notify_no_user_data(t: Namespace) -> None:
    _drain_callback_notifications(t)
    # The destroy_notify is auto-managed by the binding; callers pass
    # only the callback, mirroring pygobject's elision rules.
    assert t.test_callback_destroy_notify_no_user_data(lambda *args: 42) == 42
    assert t.test_callback_thaw_notifications() == 42


def test_test_callback_return_full(t: Namespace) -> None:
    t.test_callback_return_full(lambda: t.TestObj())


def test_test_callback_thaw_async(t: Namespace) -> None:
    _drain_callback_async(t)
    t.test_callback_async(lambda ud: 42, None)
    assert t.test_callback_thaw_async() == 42


def test_test_callback_thaw_notifications(t: Namespace) -> None:
    _drain_callback_notifications(t)


def test_test_callback_user_data(t: Namespace) -> None:
    assert t.test_callback_user_data(lambda ud: 7, object()) == 7


def test_callback_user_data_omitted_is_hidden_from_variadic_callback(
    t: Namespace,
) -> None:
    seen = []

    def callback(*args: object) -> object:
        seen.append(args)
        return 7

    assert t.test_callback_user_data(callback) == 7
    assert seen == [()]


def test_callback_user_data_explicit_none_is_delivered(t: Namespace) -> None:
    seen = []

    def callback(user_data: object) -> object:
        seen.append(user_data)
        return 7

    assert t.test_callback_user_data(callback, None) == 7
    assert seen == [None]


def test_test_closure(t: Namespace) -> None:
    t.test_closure(lambda: 0)


def test_test_closure_one_arg(t: Namespace) -> None:
    t.test_closure_one_arg(lambda x: x, 42)


def test_test_closure_variant(t: Namespace) -> None:
    t.test_closure_variant(lambda v: v, None)


# test_create_fundamental_hidden_class_instance moved to tests/test_fundamental.py.


def test_test_date_in_gvalue(t: Namespace) -> None:
    t.test_date_in_gvalue()


def test_test_def_error_quark(t: Namespace) -> None:
    t.test_def_error_quark()


def test_test_discontinuous_1_with_private_values(t: Namespace) -> None:
    t.test_discontinuous_1_with_private_values()


def test_test_discontinuous_2_with_private_values(t: Namespace) -> None:
    t.test_discontinuous_2_with_private_values()


def test_test_error_quark(t: Namespace) -> None:
    t.test_error_quark()


def test_test_filename_return(t: Namespace) -> None:
    result = t.test_filename_return()
    assert len(result) == 2


def test_test_function_async(t: Namespace) -> None:
    t.test_function_async(0, None, lambda src, res, ud: None, None)


def test_test_function_async_callback_marshals_object_args(t: Namespace) -> None:
    seen = {}
    GLib = open_namespace_for_test("auto", "GLib", "2.0")

    def callback(src: object, res: object, ud: object) -> None:
        seen["src"] = src
        seen["res"] = res
        seen["ud"] = ud

    sentinel = object()
    t.test_function_thaw_async()
    # Pass a real user_data object — None gets folded into "no
    # user_data" by the closure trampoline (same shape pygobject
    # uses for AsyncReadyCallback / Gtk.Template handlers). To
    # exercise the user_data thread-through path the caller has to
    # supply something other than None.
    t.test_function_async(0, None, callback, sentinel)
    assert t.test_function_thaw_async() >= 1
    ctx = GLib.MainContext.default()
    for _ in range(20):
        if "res" in seen:
            break
        if not ctx.pending():
            break
        ctx.iteration(False)
    assert seen["src"] is None
    assert seen["res"] is not None
    assert type(seen["res"]).__name__ == "Task"
    assert seen["ud"] is sentinel


def test_test_function_finish(t: Namespace) -> None:
    GLib = open_namespace_for_test("auto", "GLib", "2.0")
    seen = {}

    def callback(src: object, res: object, ud: object) -> None:
        seen["res"] = res

    t.test_function_thaw_async()
    t.test_function_async(0, None, callback, None)
    assert t.test_function_thaw_async() >= 1
    ctx = GLib.MainContext.default()
    for _ in range(20):
        if "res" in seen:
            break
        if not ctx.pending():
            break
        ctx.iteration(False)
    assert t.test_function_finish(seen["res"]) is True


def test_test_function_sync(t: Namespace) -> None:
    assert t.test_function_sync(0) is True


def test_test_function_thaw_async(t: Namespace) -> None:
    t.test_function_thaw_async()


# Fundamental-type coverage moved to tests/test_fundamental.py.


def test_test_garray_container_return(t: Namespace) -> None:
    assert list(t.test_garray_container_return()) == ["regress"]


def test_test_garray_full_return(t: Namespace) -> None:
    assert list(t.test_garray_full_return()) == ["regress"]


def test_test_gerror_callback(t: Namespace) -> None:
    t.test_gerror_callback(lambda err: None)


def test_test_ghash_container_return(t: Namespace) -> None:
    t.test_ghash_container_return()


def test_test_ghash_everything_return(t: Namespace) -> None:
    result = t.test_ghash_everything_return()
    assert result == {"foo": "bar", "baz": "bat", "qux": "quux"}


def test_test_ghash_gvalue_in(t: Namespace) -> None:
    t.test_ghash_gvalue_in(
        {
            "integer": 12,
            "boolean": True,
            "string": "some text",
            "strings": ["first", "second", "third"],
            "flags": t.TestFlags.FLAG1 | t.TestFlags.FLAG3,
            "enum": t.TestEnum.VALUE2,
        }
    )


def test_test_ghash_gvalue_return(t: Namespace) -> None:
    t.test_ghash_gvalue_return()


def test_test_ghash_nested_everything_return(t: Namespace) -> None:
    t.test_ghash_nested_everything_return()


def test_test_ghash_nested_everything_return2(t: Namespace) -> None:
    t.test_ghash_nested_everything_return2()


def test_test_ghash_nothing_in(t: Namespace) -> None:
    t.test_ghash_nothing_in({"foo": "bar", "baz": "bat", "qux": "quux"})


def test_test_ghash_nothing_in2(t: Namespace) -> None:
    t.test_ghash_nothing_in2({"foo": "bar", "baz": "bat", "qux": "quux"})


def test_test_ghash_nothing_return(t: Namespace) -> None:
    result = t.test_ghash_nothing_return()
    assert result == {"foo": "bar", "baz": "bat", "qux": "quux"}


def test_test_ghash_nothing_return2(t: Namespace) -> None:
    result = t.test_ghash_nothing_return2()
    assert result == {"foo": "bar", "baz": "bat", "qux": "quux"}


def test_test_ghash_null_in(t: Namespace) -> None:
    t.test_ghash_null_in(None)


def test_test_ghash_null_out(t: Namespace) -> None:
    t.test_ghash_null_out()


def test_test_ghash_null_return(t: Namespace) -> None:
    t.test_ghash_null_return()


def test_test_glist_boxed_full_return(t: Namespace) -> None:
    result = t.test_glist_boxed_full_return(3)
    assert len(list(result)) == 3


def test_test_glist_boxed_none_return(t: Namespace) -> None:
    # Regress caches this transfer-none list in a static C variable and only
    # honors count on the first non-empty call. Other tests may have already
    # initialized it in this worker process.
    existing = list(t.test_glist_boxed_none_return(0))
    expected_len = len(existing) or 3
    result = t.test_glist_boxed_none_return(3)
    assert len(list(result)) == expected_len


def test_test_glist_container_return(t: Namespace) -> None:
    t.test_glist_container_return()


def test_test_glist_everything_return(t: Namespace) -> None:
    assert list(t.test_glist_everything_return()) == ["1", "2", "3"]


def test_test_glist_gtype_container_in(t: Namespace) -> None:
    obj_gtype = t.TestObj.gimeta.gtype
    sub_gtype = t.TestSubObj.gimeta.gtype
    t.test_glist_gtype_container_in([obj_gtype, sub_gtype])


def test_test_glist_nothing_in(t: Namespace) -> None:
    t.test_glist_nothing_in(["1", "2", "3"])


def test_test_glist_nothing_in2(t: Namespace) -> None:
    t.test_glist_nothing_in2(["1", "2", "3"])


def test_test_glist_nothing_return(t: Namespace) -> None:
    assert list(t.test_glist_nothing_return()) == ["1", "2", "3"]


def test_test_glist_nothing_return2(t: Namespace) -> None:
    assert list(t.test_glist_nothing_return2()) == ["1", "2", "3"]


def test_test_glist_null_in(t: Namespace) -> None:
    t.test_glist_null_in(None)


def test_test_glist_null_out(t: Namespace) -> None:
    t.test_glist_null_out()


def test_test_gslist_container_return(t: Namespace) -> None:
    t.test_gslist_container_return()


def test_test_gslist_everything_return(t: Namespace) -> None:
    assert list(t.test_gslist_everything_return()) == ["1", "2", "3"]


def test_test_gslist_nothing_in(t: Namespace) -> None:
    t.test_gslist_nothing_in(["1", "2", "3"])


def test_test_gslist_nothing_in2(t: Namespace) -> None:
    t.test_gslist_nothing_in2(["1", "2", "3"])


def test_test_gslist_nothing_return(t: Namespace) -> None:
    assert list(t.test_gslist_nothing_return()) == ["1", "2", "3"]


def test_test_gslist_nothing_return2(t: Namespace) -> None:
    assert list(t.test_gslist_nothing_return2()) == ["1", "2", "3"]


def test_test_gslist_null_in(t: Namespace) -> None:
    t.test_gslist_null_in(None)


def test_test_gslist_null_out(t: Namespace) -> None:
    t.test_gslist_null_out()


def test_test_gvalue_out_boxed(t: Namespace) -> None:
    assert t.test_gvalue_out_boxed(7) is not None


def test_test_gvariant_as(t: Namespace) -> None:
    v = t.test_gvariant_as()
    assert v is not None


def test_test_gvariant_asv(t: Namespace) -> None:
    v = t.test_gvariant_asv()
    assert v is not None


def test_test_gvariant_i(t: Namespace) -> None:
    v = t.test_gvariant_i()
    assert v is not None


def test_test_gvariant_s(t: Namespace) -> None:
    v = t.test_gvariant_s()
    assert v is not None


def test_test_gvariant_v(t: Namespace) -> None:
    v = t.test_gvariant_v()
    assert v is not None


def test_test_hash_table_callback(t: Namespace) -> None:
    t.test_hash_table_callback({"-1": -1, "0": 0, "1": 1}, lambda h: None)


def test_test_int_out_utf8(t: Namespace) -> None:
    t.test_int_out_utf8("hello")


def test_test_int_value_arg(t: Namespace) -> None:
    assert t.test_int_value_arg(42) == 42


def test_test_multi_callback(t: Namespace) -> None:
    t.test_multi_callback()


def test_test_multi_double_args(t: Namespace) -> None:
    one, two = t.test_multi_double_args(3.0)
    assert one == pytest.approx(6.0)
    assert two == pytest.approx(9.0)


def test_test_multiline_doc_comments(t: Namespace) -> None:
    t.test_multiline_doc_comments()


def test_test_nested_parameter(t: Namespace) -> None:
    t.test_nested_parameter(0)


def test_test_noptr_callback(t: Namespace) -> None:
    t.test_noptr_callback()


def test_test_null_gerror_callback(t: Namespace) -> None:
    t.test_null_gerror_callback(lambda err: None)


def test_test_null_strv_in_gvalue(t: Namespace) -> None:
    t.test_null_strv_in_gvalue()


def test_test_owned_gerror_callback(t: Namespace) -> None:
    t.test_owned_gerror_callback(lambda err: None)


def test_test_simple_boxed_a_const_return(t: Namespace) -> None:
    t.test_simple_boxed_a_const_return()


def test_test_simple_callback(t: Namespace) -> None:
    called = []
    t.test_simple_callback(lambda: called.append(1))
    assert called == [1]
    t.test_simple_callback(None)


def test_test_struct_a_parse(t: Namespace) -> None:
    t.test_struct_a_parse("1,2,3,4,5")


def test_test_strv_in(t: Namespace) -> None:
    assert t.test_strv_in(["1", "2", "3"]) is True


def test_test_strv_in_gvalue(t: Namespace) -> None:
    assert list(t.test_strv_in_gvalue()) == ["one", "two", "three"]


def test_test_strv_out(t: Namespace) -> None:
    assert t.test_strv_out() == ["thanks", "for", "all", "the", "fish"]


def test_test_strv_out_c(t: Namespace) -> None:
    assert list(t.test_strv_out_c()) == ["thanks", "for", "all", "the", "fish"]


def test_test_strv_out_container(t: Namespace) -> None:
    assert list(t.test_strv_out_container()) == ["1", "2", "3"]


def test_test_strv_outarg(t: Namespace) -> None:
    assert list(t.test_strv_outarg()) == ["1", "2", "3"]


def test_test_torture_signature_0(t: Namespace) -> None:
    y, z, q = t.test_torture_signature_0(5, "hello", 2)
    assert y == pytest.approx(5.0)
    assert z == 10
    assert q == 7


def test_test_torture_signature_1(t: Namespace) -> None:
    # `(success: bool, y: double, z: int, q: int)` — pygobject shape now
    # that bool-no-throws keeps OUTs.
    ok, y, z, q = t.test_torture_signature_1(5, "hello", 2)
    assert ok is True
    assert y == pytest.approx(5.0)
    assert z == 10
    assert q == 7


def test_test_torture_signature_2(t: Namespace) -> None:
    # destroy_notify is auto-managed; callers omit it (pygobject elision).
    t.test_torture_signature_2(5, lambda *args: 0, None, "hello", 2)


def test_test_unconventional_error_quark(t: Namespace) -> None:
    t.test_unconventional_error_quark()


def test_test_value_return(t: Namespace) -> None:
    assert t.test_value_return(42) == 42


def test_test_versioning(t: Namespace) -> None:
    assert t.test_versioning() is None
