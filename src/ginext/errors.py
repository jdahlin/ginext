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

"""Python exception wrappers for GLib.GError."""

from __future__ import annotations

import builtins
from types import SimpleNamespace
from typing import Any, cast

from . import features


def _domain_to_string(domain: object) -> object:
    if isinstance(domain, str) or domain is None:
        return domain
    if isinstance(domain, int):
        try:
            from ginext import GLib

            name = GLib.quark_to_string(domain)
        except AttributeError, ImportError, RuntimeError:
            return str(domain)
        return name if name is not None else str(domain)
    return domain


def _domain_matches(stored: object, requested: object) -> bool:
    if stored == requested:
        return True
    return _domain_to_string(stored) == _domain_to_string(requested)


def _code_to_int(code: object) -> int | object:
    try:
        return int(cast("Any", code))
    except ValueError:
        return code


class Error(RuntimeError):
    """Structured Python representation of a GLib GError."""

    def __init__(self, message: object = "", domain: object = None, code: int = 0):
        self.message = message if message is not None else ""
        self.domain = domain
        self.code = code
        super().__init__(self.message)

    @classmethod
    def new_literal(cls, domain: object, *args: object) -> Error:
        if len(args) != 2:
            raise TypeError(
                "GLib.Error.new_literal(domain, message, code) expects 3 arguments"
            )
        first, second = args
        code: object
        if isinstance(first, int) and not isinstance(second, int):
            code = first
            message = second
        else:
            message = first
            code = second
        return cls(message, _domain_to_string(domain), int(cast("Any", code)))

    def matches(self, domain: object, code: object | None = None) -> bool:
        if code is None:
            return self.code == _code_to_int(domain)
        return _domain_matches(self.domain, domain) and _code_to_int(
            self.code
        ) == _code_to_int(code)

    def __str__(self) -> str:
        return f"{self.domain}: {self.message} ({self.code})"

    def __repr__(self) -> str:
        return f"GLib.Error({self.message!r}, {self.domain!r}, {self.code!r})"


_GIO_BUILTIN_CODE_MAP = {
    "NOT_FOUND": ("NotFoundError", builtins.FileNotFoundError),
    "EXISTS": ("FileExistsError", builtins.FileExistsError),
    "IS_DIRECTORY": ("IsADirectoryError", builtins.IsADirectoryError),
    "NOT_DIRECTORY": ("NotADirectoryError", builtins.NotADirectoryError),
    "PERMISSION_DENIED": ("PermissionDeniedError", builtins.PermissionError),
    "CANCELLED": ("CancelledError", builtins.InterruptedError),
    "BROKEN_PIPE": ("BrokenPipeError", builtins.BrokenPipeError),
    "CONNECTION_REFUSED": ("ConnectionRefusedError", builtins.ConnectionRefusedError),
    "NO_SPACE": ("NoSpaceError", builtins.OSError),
    "TIMED_OUT": ("TimedOutError", builtins.TimeoutError),
}


def install_glib_error_class(GLib: object) -> None:
    _glib: Any = GLib
    _glib.Error = Error
    _glib.GError = Error


def install_gio_error_classes(Gio: object) -> None:
    _gio: Any = Gio
    install_glib_error_class(__import__("ginext").GLib)
    try:
        errors = _gio.errors
    except AttributeError:
        errors = SimpleNamespace()
        _gio.errors = errors

    if not hasattr(errors, "IOError"):
        _dq = _gio.io_error_quark()
        _dn = __import__("ginext").GLib.quark_to_string(_dq)

        class IOError(Error):
            domain_enum = _gio.IOErrorEnum
            domain_quark = _dq
            domain_name = _dn

            @property
            def code_enum(self) -> object:
                try:
                    return _gio.IOErrorEnum(int(self.code))
                except ValueError:
                    return None

            def matches(self, domain: object, code: object | None = None) -> bool:
                if code is None and isinstance(domain, _gio.IOErrorEnum):
                    return int(self.code) == int(domain)
                return super().matches(domain, code)

        errors.IOError = IOError

    base = errors.IOError
    for enum_name, (class_name, builtin_base) in _GIO_BUILTIN_CODE_MAP.items():
        if not hasattr(_gio.IOErrorEnum, enum_name) or hasattr(_gio, class_name):
            continue
        enum_value = getattr(_gio.IOErrorEnum, enum_name)
        cls = type(
            class_name,
            (base, builtin_base),
            {
                "__module__": "ginext.Gio",
                "code_enum": enum_value,
            },
        )
        setattr(_gio, class_name, cls)
        setattr(errors, class_name, cls)


def _gio_exception_class(domain: int, code: int) -> type[Error] | None:
    if not features.is_enabled(features.GERROR_BUILTIN_EXCEPTIONS):
        return None
    try:
        from ginext import Gio
    except ImportError, RuntimeError:
        return None
    if int(domain) != int(Gio.io_error_quark()):
        return None
    install_gio_error_classes(Gio)
    for enum_name, (class_name, _builtin_base) in _GIO_BUILTIN_CODE_MAP.items():
        if hasattr(Gio.IOErrorEnum, enum_name) and int(
            getattr(Gio.IOErrorEnum, enum_name)
        ) == int(code):
            return cast("type[Error]", getattr(Gio, class_name))
    try:
        return cast("type[Error] | None", Gio.errors.IOError)
    except AttributeError:
        return None


def _exception_from_gerror(domain: int, code: int, message: str | None) -> Error:
    cls = _gio_exception_class(domain, code) or Error
    return cls(message or "", _domain_to_string(domain), int(code))


def _raise_gerror(domain: int, code: int, message: str | None) -> None:
    raise _exception_from_gerror(domain, code, message)


__all__ = [
    "Error",
    "install_glib_error_class",
    "install_gio_error_classes",
]
