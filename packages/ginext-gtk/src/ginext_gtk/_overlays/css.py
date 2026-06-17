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

"""CssProvider overlay, Gtk init hook, and main_quit."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ginext import Gtk

if TYPE_CHECKING:
    from collections.abc import Callable

overlay = Gtk.overlay


def _css_data_bytes(data: str | bytes | bytearray, length: int) -> bytes:
    if isinstance(data, str):
        raw = data.encode("utf-8")
    else:
        raw = bytes(data)
    if length >= 0:
        return bytes(raw[:length])
    return bytes(raw)


# ---------------------------------------------------------------------------
# GTK auto-init on first namespace access
# ---------------------------------------------------------------------------


def _gtk_auto_init() -> None:
    # init_check is version-polymorphic (GTK3 takes argv, GTK4 takes none);
    # resolve it dynamically so either arity type-checks.
    init_check = Gtk.init_check
    ok = init_check([]) if Gtk.__version__[0] == 3 else init_check()
    if isinstance(ok, tuple):
        ok = ok[0]
    Gtk._ginext_display_available = bool(ok)


overlay.on_first_access(
    _gtk_auto_init,
    env_gate="GINEXT_GTK_AUTO_INIT",
    on_error="warn",
)


# ---------------------------------------------------------------------------
# main_quit
# ---------------------------------------------------------------------------


def _main_quit_replace(fn: Callable[[], None], *_args: object) -> None:
    return fn()


try:
    overlay.replace(_main_quit_replace)
except ValueError:

    def _main_quit_add(*_args: object) -> None:
        return None

    overlay.add(_main_quit_add)


# ---------------------------------------------------------------------------
# CssProvider
# ---------------------------------------------------------------------------


@overlay.method("CssProvider")
def load_from_data(
    fn: Callable[[Gtk.CssProvider, bytes, int], None],
    self: Gtk.CssProvider,
    data: str | bytes | bytearray,
    length: int = -1,
) -> None:
    if Gtk.__version__[0] == 3:
        # GTK3 load_from_data takes only (data); the stub models GTK4's arity.
        fn(self, _css_data_bytes(data, length))  # type: ignore[call-arg]
        return
    payload = bytes(data) if isinstance(data, bytearray) else data
    fn(self, payload, length)  # type: ignore[arg-type]
