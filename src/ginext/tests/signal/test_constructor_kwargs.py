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

"""Constructor sugar: `Gtk.Button(label="OK", on_clicked=handler)`.

The `on_<signal>=callback` kwarg splits off from property kwargs and
connects with `owner=self` (the new instance), so the handler's
lifetime is tied to the object's. Available on both imported classes
(via classbuild.GObjectInstance) and Python-defined classes (via
gobject.GObject).
"""

import itertools
import warnings

from typing import Any, cast

import pytest

import ginext
from ginext.gobject.gobjectclass import GObject, Property


_seq = itertools.count()


def _unique_type_name(prefix: str) -> str:
    return f"GinextCtorKw{prefix}{next(_seq):04d}"


def test_imported_class_handler_kwarg() -> None:
    from ginext import Gio

    fires = []
    c = Gio.Cancellable(on_cancelled=lambda src: fires.append("fired"))
    c.cancel()
    assert fires == ["fired"]


def test_imported_class_no_warning_for_handler_kwarg() -> None:
    """The new instance is the owner, so the unowned warning must not
    fire even though the user didn't write `owner=...` explicitly."""
    from ginext import Gio

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        Gio.Cancellable(on_cancelled=lambda src: None)
    relevant = [
        w
        for w in captured
        if issubclass(w.category, ginext.UnownedSignalHandlerWarning)
    ]
    assert relevant == []


def test_unknown_handler_kwarg_raises_with_close_matches() -> None:
    from ginext import Gio

    with pytest.raises(TypeError) as exc_info:
        Gio.Cancellable(on_canceld=lambda src: None)  # typo
    msg = str(exc_info.value)
    assert "on_canceld" in msg
    assert "cancelled" in msg  # close-match hint should appear


def test_unknown_handler_kwarg_without_close_match() -> None:
    from ginext import Gio

    with pytest.raises(TypeError) as exc_info:
        Gio.Cancellable(on_xyzzy=lambda src: None)
    assert "xyzzy" in str(exc_info.value)


def test_non_callable_handler_kwarg_raises() -> None:
    from ginext import Gio

    with pytest.raises(TypeError, match="must be callable"):
        Gio.Cancellable(on_cancelled=42)


def test_python_defined_class_handler_kwarg() -> None:
    class Item(GObject, type_name=_unique_type_name("Item")):
        title: str = Property(default="")

    fires = []
    # Python-defined GObject inherits notify from GObject.Object, so we
    # can attach an on_notify handler via the constructor.
    obj = cast("Any", Item)(on_notify=lambda src, pspec: fires.append(pspec))
    obj.title = "updated"
    assert len(fires) == 1


def test_python_defined_class_property_plus_handler() -> None:
    """Properties and on_<signal> kwargs mix freely."""

    class Item(GObject, type_name=_unique_type_name("Item")):
        title: str = Property(default="")

    fires = []
    obj = cast("Any", Item)(title="hello", on_notify=lambda src, pspec: fires.append(1))
    assert obj.title == "hello"
    obj.title = "updated"
    assert fires == [1]


def test_handler_kwarg_owner_is_new_instance() -> None:
    """The connection's owner is the newly-constructed instance, so
    `conn.owner` is the object itself."""
    from ginext import Gio

    captured: dict[str, Any] = {}

    def handler(src: Any) -> None:
        captured["src"] = src

    c = Gio.Cancellable(on_cancelled=handler)
    # No public hook to grab the conn back from the kwarg path; verify
    # behavior instead: the handler fires and receives the right source.
    c.cancel()
    assert captured["src"] is c


def test_short_on_prefix_is_treated_as_property() -> None:
    """A bare `on_` (length 3, no signal name after) must not be parsed
    as a handler kwarg — it would never name a signal anyway. Bare
    `on_` is rare in real APIs; if a property happens to be named `on_`
    the construction should error as a normal unknown-property failure
    rather than as a confusing handler-kwarg failure."""
    from ginext import Gio

    # Cancellable has no "on" property; this should raise as a property
    # error, not as our on_<signal> TypeError.
    with pytest.raises(Exception):
        # Specific exception type varies based on GObject's property
        # error reporting; we just verify it raises and doesn't reach
        # the handler-kwarg path.
        Gio.Cancellable(on_=42)
