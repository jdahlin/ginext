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

"""GLib.Error coverage ported from legacy goi tests."""

from __future__ import annotations


def test_glib_error_class_exists() -> None:
    from ginext import GLib

    assert hasattr(GLib, "Error")
    assert isinstance(GLib.Error, type)


def test_glib_error_is_exception_subclass() -> None:
    from ginext import GLib

    assert issubclass(GLib.Error, BaseException)


def test_except_glib_error_does_not_raise_typeerror() -> None:
    from ginext import GLib

    try:
        raise ValueError("inner")
    except GLib.Error:
        pass
    except ValueError:
        pass


def test_glib_error_carries_domain_code_message() -> None:
    from ginext import GLib

    error = GLib.Error.new_literal("test-domain", 42, "boom")

    assert error.domain == "test-domain"
    assert error.code == 42
    assert error.message == "boom"
    assert error.matches("test-domain", 42)
    assert not error.matches("other-domain", 42)


def test_glib_error_raise_and_catch() -> None:
    from ginext import GLib

    try:
        raise GLib.Error.new_literal("io", 1, "bang")
    except GLib.Error as error:
        assert error.code == 1
        assert error.message == "bang"


def test_matches_accepts_gquark_int() -> None:
    from ginext import GLib

    error = GLib.Error.new_literal("g-io-error-quark", 1, "not found")
    quark = GLib.quark_from_string("g-io-error-quark")

    assert error.matches(quark, 1)
    assert not error.matches(quark, 2)


def test_matches_accepts_string_and_int_form() -> None:
    from ginext import GLib

    error = GLib.Error.new_literal("test-domain", 7, "x")
    quark = GLib.quark_from_string("test-domain")

    assert error.matches("test-domain", 7)
    assert error.matches(quark, 7)


def test_new_literal_accepts_quark_int_domain() -> None:
    from ginext import GLib

    quark = GLib.quark_from_string("test-int-domain")
    error = GLib.Error.new_literal(quark, 5, "boom")

    assert error.domain == "test-int-domain"
    assert error.matches(quark, 5)


def test_gio_not_found_maps_to_builtin_file_not_found() -> None:
    from ginext import features, GLib, Gio
    from ginext.errors import _exception_from_gerror

    features.set_enabled(features.GERROR_BUILTIN_EXCEPTIONS, True)
    try:
        error = _exception_from_gerror(
            Gio.io_error_quark(), int(Gio.IOErrorEnum.NOT_FOUND), "missing"
        )
    finally:
        features.reset_for_test()

    assert isinstance(error, GLib.Error)
    assert isinstance(error, Gio.NotFoundError)
    assert isinstance(error, FileNotFoundError)
    assert error.domain == "g-io-error-quark"
    assert error.matches(Gio.IOErrorEnum.NOT_FOUND)


def test_pygobject_compat_disables_builtin_error_mapping_by_default() -> None:
    from ginext import features, Gio, GLib
    from ginext.errors import _exception_from_gerror

    features.configure({features.PYGOBJECT_COMPAT: True})
    try:
        error = _exception_from_gerror(
            Gio.io_error_quark(), int(Gio.IOErrorEnum.NOT_FOUND), "missing"
        )
    finally:
        features.reset_for_test()

    assert isinstance(error, GLib.Error)
    assert not isinstance(error, FileNotFoundError)
