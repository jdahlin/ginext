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

"""Native (non-pygobject) coverage for `inspect.signature()` on GI callables.

Drives `ginext.signature` directly against the gobject-introspection test
namespaces, asserting ginext's own signature model — IN/INOUT params typed from
the GI type tags, OUT/INOUT folded into a `tuple[...]` return, companion args
(array length, callback user_data/destroy) hidden, nullable args defaulting to
None. The PyGObject-compat suite checks PyGObject-compatibility separately; this
suite locks the core contract on its own terms.
"""

from __future__ import annotations

import inspect
import sys
import types
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar, cast

import pytest

from ginext import signature
from ginext.namespace import Namespace
from ginext.tests.gi_test_utils import load_test_namespace


@pytest.fixture(scope="module")
def gim() -> Namespace:
    return load_test_namespace("GIMarshallingTests")


@pytest.fixture(scope="module")
def regress() -> Namespace:
    return load_test_namespace("Regress")


@pytest.fixture
def namespaces(gim: Namespace, regress: Namespace) -> dict[str, Namespace]:
    return {"gim": gim, "regress": regress}


def _resolve(
    namespaces: dict[str, Namespace], ns: str, target: str
) -> Callable[..., object]:
    result: object = namespaces[ns]
    for part in target.split("."):
        result = getattr(result, part)
    return cast("Callable[..., object]", result)


@dataclass(frozen=True)
class SigCase:
    id: str
    ns: str
    target: str
    expected: str


# str(inspect.signature(...)) for a representative callable per code path. Each
# row exercises a distinct branch of ginext.signature; see the trailing comments.
SIG_CASES = [
    # scalars / strings / void return
    SigCase("scalar_str_in", "gim", "utf8_none_in", "(utf8: str) -> None"),
    SigCase("scalar_str_return", "gim", "utf8_full_return", "() -> str"),
    # an INOUT scalar is both a parameter and (the sole) return value
    SigCase("scalar_int_inout", "gim", "int_inout_max_min", "(int_: int) -> int"),
    # arrays (IN drops the implicit length arg; OUT; INOUT)
    SigCase("array_in", "gim", "array_in", "(ints: list[int]) -> None"),
    SigCase("array_out", "gim", "array_out", "() -> list[int]"),
    SigCase("array_inout", "gim", "array_inout", "(ints: list[int]) -> list[int]"),
    SigCase(
        "array_zero_term_return",
        "gim",
        "array_zero_terminated_return",
        "() -> list[str]",
    ),
    # GList / GSList / GHashTable
    SigCase("glist_int", "gim", "glist_int_none_return", "() -> list[int]"),
    SigCase("gslist_int", "gim", "gslist_int_none_return", "() -> list[int]"),
    SigCase("ghash_int", "gim", "ghashtable_int_none_return", "() -> dict[int, int]"),
    SigCase("glist_utf8", "gim", "glist_utf8_none_return", "() -> list[str]"),
    # interface types: enum / flags resolved to their Python class
    SigCase("enum_in", "gim", "enum_in", "(v: GIMarshallingTests.Enum) -> None"),
    SigCase("enum_out", "gim", "enum_out", "() -> GIMarshallingTests.Enum"),
    SigCase("flags_in", "gim", "flags_in", "(v: GIMarshallingTests.Flags) -> None"),
    # GType / GValue have no name in the native profile -> graceful Any
    SigCase("gtype_in_any", "gim", "gtype_in", "(gtype: Any) -> None"),
    SigCase("gvalue_in_any", "gim", "gvalue_in", "(value: Any) -> None"),
    SigCase("gtype_out_any", "gim", "gtype_out", "() -> Any"),
    # GError tag resolves to the live error class
    SigCase("gerror_out", "gim", "gerror_out", "() -> tuple[ginext.errors.Error, str]"),
    SigCase("gerror_return", "gim", "gerror_return", "() -> ginext.errors.Error"),
    # nullable array param defaults to None; multi-result tuple keeps the | None
    SigCase(
        "nullable_array_default",
        "gim",
        "init_function",
        "(argv: list[str] | None = None) -> tuple[bool, list[str] | None]",
    ),
    # a nullable C return value carries the | None on the return annotation
    SigCase(
        "nullable_return",
        "gim",
        "filename_copy",
        "(path_in: str | None = None) -> str | None",
    ),
    # OUT/INOUT folding into a tuple return
    SigCase("multi_out_tuple", "gim", "int_out_out", "() -> tuple[int, int]"),
    SigCase("ret_and_out_tuple", "gim", "int_return_out", "() -> tuple[int, int]"),
    # callbacks: Callable[...] annotation, companion user_data/destroy hidden
    SigCase(
        "callback_optional",
        "regress",
        "test_callback",
        "(callback: collections.abc.Callable[[], int] | None = None) -> int",
    ),
    SigCase(
        "callback_user_data_skip",
        "regress",
        "test_callback_user_data",
        "(callback: collections.abc.Callable[[None], int]) -> int",
    ),
    SigCase(
        "callback_destroy_skip",
        "regress",
        "test_callback_destroy_notify",
        "(callback: collections.abc.Callable[[None], int]) -> int",
    ),
    SigCase(
        "callback_void_ret",
        "regress",
        "test_simple_callback",
        "(callback: collections.abc.Callable[[], None] | None = None) -> None",
    ),
    # methods carry a leading `self`
    SigCase(
        "method_array_in",
        "gim",
        "Object.method_array_in",
        "(self, ints: list[int]) -> None",
    ),
    SigCase(
        "method_array_out", "gim", "Object.method_array_out", "(self) -> list[int]"
    ),
    SigCase(
        "method_array_return_tuple",
        "gim",
        "Object.method_array_return",
        "(self) -> tuple[list[int], int]",
    ),
    SigCase(
        "method_arg_and_out",
        "gim",
        "Object.method_int8_arg_and_out_callee",
        "(self, arg: int) -> int",
    ),
    SigCase(
        "method_str_arg_out_ret",
        "gim",
        "Object.method_str_arg_out_ret",
        "(self, arg: str) -> tuple[str, int]",
    ),
    # arg literally named `in` is sanitised to `in_`
    SigCase(
        "method_keyword_arg", "gim", "Object.method_int8_in", "(self, in_: int) -> None"
    ),
    SigCase(
        "vfunc_return_only", "gim", "Object.vfunc_return_value_only", "(self) -> int"
    ),
    # constructors are static (no self)
    SigCase(
        "ctor_new", "gim", "Object.new", "(int_: int) -> GIMarshallingTests.Object"
    ),
    SigCase(
        "ctor_from_file",
        "regress",
        "TestObj.new_from_file",
        "(x: str) -> Regress.TestObj",
    ),
]


@pytest.mark.parametrize("case", SIG_CASES, ids=lambda case: case.id)
def test_signature_matches(namespaces: dict[str, Namespace], case: SigCase) -> None:
    callable_ = _resolve(namespaces, case.ns, case.target)
    assert str(inspect.signature(callable_)) == case.expected


class TestCallableBehaviour:
    def test_module_function_is_introspectable(self, gim: Namespace) -> None:
        # ginext.method.Function exposes __signature__ as a property.
        sig = inspect.signature(gim.array_in)
        assert list(sig.parameters) == ["ints"]
        assert sig.return_annotation is None

    def test_unbound_method_keeps_self(self, gim: Namespace) -> None:
        sig = inspect.signature(gim.Object.method_array_in)
        assert list(sig.parameters) == ["self", "ints"]

    def test_bound_method_drops_self(self, gim: Namespace) -> None:
        instance = gim.Object.new(42)
        sig = inspect.signature(instance.method_array_in)
        assert list(sig.parameters) == ["ints"]

    def test_signature_is_cached(self, gim: Namespace) -> None:
        fn = gim.array_in
        # The Signature is memoised on gimeta, so repeated lookups are identical.
        assert fn.__signature__ is fn.__signature__

    def test_callable_signature_helper_memoises(self, gim: Namespace) -> None:
        gimeta = gim.utf8_none_in.gimeta
        gimeta.signature = None
        first = signature.callable_signature(gimeta)
        assert gimeta.signature is first
        assert signature.callable_signature(gimeta) is first


class TestReturnFolding:
    def test_single_out_collapses_to_scalar(self, gim: Namespace) -> None:
        sig = inspect.signature(gim.array_out)
        assert sig.return_annotation == list[int]

    def test_multiple_outs_become_tuple(self, gim: Namespace) -> None:
        sig = inspect.signature(gim.int_out_out)
        assert sig.return_annotation == tuple[int, int]

    def test_void_with_no_out_is_none(self, gim: Namespace) -> None:
        sig = inspect.signature(gim.utf8_none_in)
        assert sig.return_annotation is None


class TestNullability:
    def test_nullable_arg_defaults_to_none(self, gim: Namespace) -> None:
        param = inspect.signature(gim.init_function).parameters["argv"]
        assert param.default is None
        assert param.annotation == list[str] | None

    def test_non_nullable_arg_has_no_default(self, gim: Namespace) -> None:
        param = inspect.signature(gim.array_in).parameters["ints"]
        assert param.default is inspect.Parameter.empty


class TestSafeParamName:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("ints", "ints"),
            ("value", "value"),
            ("in", "in_"),
            ("class", "class_"),
            ("lambda", "lambda_"),
            ("from", "from_"),
            # soft keywords are valid identifiers and are left untouched
            ("type", "type"),
            ("match", "match"),
        ],
    )
    def test_keyword_names_are_suffixed(self, name: str, expected: str) -> None:
        assert signature._safe_param_name(name) == expected


class TestMaybeOptional:
    def test_non_nullable_keeps_annotation_and_empty_default(self) -> None:
        annotation, default = signature._maybe_optional(int, nullable=False)
        assert annotation is int
        assert default is inspect.Parameter.empty

    def test_nullable_unions_with_none_and_defaults_none(self) -> None:
        annotation, default = signature._maybe_optional(int, nullable=True)
        assert annotation == int | None
        assert default is None


class FakeType:
    """Minimal GITypeInfo stand-in exposing only `get_tag()`."""

    def __init__(self, tag: int) -> None:
        self._tag = tag

    def get_tag(self) -> int:
        return self._tag


class FakeInfo:
    """Minimal callable info whose `arg_names` references a non-existent arg."""

    arg_names: ClassVar[list[str]] = ["ghost"]

    def get_n_args(self) -> int:
        return 0

    def get_return_type(self) -> FakeType:
        return FakeType(0)  # _VOID

    def skip_return(self) -> bool:
        return False

    def may_return_null(self) -> bool:
        return False


class TestFallbacks:
    """Defensive branches that no real typelib reaches, driven with stubs."""

    def test_unknown_tag_maps_to_any(self) -> None:
        # A tag outside the known set degrades to Any rather than raising.
        assert signature.annotation_for_type(FakeType(999), context=None) is Any

    def test_arg_name_without_arginfo_becomes_plain_param(self) -> None:
        # arg_names listing a name with no matching GIArgInfo yields a bare,
        # un-annotated parameter (and a void return collapses to None).
        sig = signature.build_signature(FakeInfo(), has_self=False, context=None)
        assert list(sig.parameters) == ["ghost"]
        assert sig.parameters["ghost"].annotation is inspect.Parameter.empty
        assert sig.return_annotation is None

    def test_error_type_falls_back_to_any_when_unresolvable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(name: str, context: object) -> object:
            raise AttributeError(name)

        monkeypatch.setattr(signature, "_resolve_namespace", boom)
        assert (
            signature.annotation_for_type(FakeType(20), context=None) is Any
        )  # _ERROR

    def test_resolve_namespace_without_version_uses_ginext_attr(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import ginext.errors  # noqa: F401  (ensure the submodule is importable)
        from ginext import defaults

        monkeypatch.setattr(defaults, "resolve_version", lambda name: None)
        context = types.SimpleNamespace(name="GIMarshallingTests")
        resolved = signature._resolve_namespace("errors", context)
        assert resolved is sys.modules["ginext"].errors
