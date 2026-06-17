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

"""GObject signal connect tests.

Modeled on pygobject's `tests/test_signal.py::TestClosures` with two
twists:

  * Pytest fixtures + parametrization in place of unittest classes.
  * Driven by C-defined signals on Gio.Cancellable / Gio.SimpleAction
    (no display, no event loop). goi doesn't yet support Python-side
    `__gsignals__` / `GObject.Signal()`, so the tests use existing
    typelib signals to exercise the runtime plumbing.

Centerpiece is the GObject-overlay-driven trailing-user-data behavior:
`obj.connect(signal, handler, *user_data)` forwards the extras as
trailing args on every callback invocation. That's pygobject's
historical signature; goi's C-level connect is strict by default and
the GObject-2.0.toml overlay flips a sticky flag to broaden it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Generator, Protocol

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    class _SignalSource(Protocol):
        """The slice of the GObject signal API these tests drive on a
        Gio.Cancellable. (The generated Gio stub types `connect` with precise
        per-signal overloads that reject the dynamic
        `connect(name, handler, *user_data)` form exercised here.)"""

        def connect(  # type: ignore[explicit-any]
            self,
            signal: str,
            handler: Callable[..., object],
            *user_data: object,
            owner: object = ...,
        ) -> object: ...
        def connect_after(  # type: ignore[explicit-any]
            self,
            signal: str,
            handler: Callable[..., object],
            *user_data: object,
            owner: object = ...,
        ) -> object: ...
        def cancel(self) -> None: ...


@pytest.fixture(autouse=True)
def _old_signal_api() -> Generator[None]:
    from ginext import features

    features.set_enabled(features.OLD_SIGNAL_API, True)
    yield
    features.set_enabled(features.OLD_SIGNAL_API, False)


# --- Trailing user_data forwarding --------------------------------------


@pytest.mark.parametrize(
    ("user_data", "expected_extras"),
    [
        ((), ()),
        (("alpha",), ("alpha",)),
        ((42,), (42,)),
        (("a", 1, None, [1, 2]), ("a", 1, None, [1, 2])),
    ],
    ids=["zero", "one-str", "one-int", "four-mixed"],
)
def test_connect_forwards_user_data(
    cancellable: _SignalSource,
    user_data: tuple[object, ...],
    expected_extras: tuple[object, ...],
) -> None:
    """The handler receives `(signal_args..., *user_data)` on every call.
    Zero user_data is the legacy strict path; non-zero exercises the
    overlay-enabled trampoline. Both flow through the same connect().
    """
    seen = []

    def handler(c: object, *extras: object) -> None:
        seen.append((c is cancellable, extras))

    cancellable.connect("cancelled", handler, *user_data, owner=cancellable)
    cancellable.cancel()
    assert seen == [(True, expected_extras)]


def test_connect_after_forwards_user_data(cancellable: _SignalSource) -> None:
    """connect_after walks the same trampoline path."""
    seen = []

    def handler(c: object, mark: object) -> None:
        seen.append(mark)

    cancellable.connect_after("cancelled", handler, "after-mark", owner=cancellable)
    cancellable.cancel()
    assert seen == ["after-mark"]


def test_handler_id_increments(cancellable: _SignalSource) -> None:
    """connect returns a non-zero handler id; subsequent connects
    return distinct ids on the same object."""
    h1 = cancellable.connect("cancelled", lambda c: None, owner=cancellable)
    h2 = cancellable.connect("cancelled", lambda c: None, "extra", owner=cancellable)
    assert h1 != 0 and h2 != 0
    assert h1 != h2


def test_multiple_handlers_all_fire(cancellable: _SignalSource) -> None:
    """All connected handlers run on a single signal emission."""
    seen = []
    cancellable.connect("cancelled", lambda c: seen.append("a"), owner=cancellable)
    cancellable.connect(
        "cancelled", lambda c, mark: seen.append(mark), "b", owner=cancellable
    )
    cancellable.connect_after(
        "cancelled", lambda c: seen.append("after"), owner=cancellable
    )
    cancellable.cancel()
    # Order: connect-before handlers fire in connect order, then connect_after.
    assert seen == ["a", "b", "after"]


# --- Rejection paths -----------------------------------------------------


@pytest.mark.parametrize(
    ("args", "match"),
    [
        ((), "connect"),  # no signal name
        (("cancelled",), "connect"),  # no handler
        ((42, lambda c: None), "must be a str"),  # signal name not a str
        (("cancelled", "not-callable"), "callable"),  # handler not callable
    ],
    ids=["no-args", "no-handler", "signal-not-str", "handler-not-callable"],
)
def test_connect_rejects_bad_args(
    cancellable: _SignalSource, args: tuple[object, ...], match: str
) -> None:
    with pytest.raises(TypeError, match=match):
        cancellable.connect(*args)  # type: ignore[arg-type]


test_connect_rejects_bad_args = pytest.mark.filterwarnings(
    "ignore:connecting .* without an owner:ginext.signal.connection.UnownedSignalHandlerWarning"
)(test_connect_rejects_bad_args)


def test_connect_rejects_unknown_signal(cancellable: _SignalSource) -> None:
    """Connecting to a non-existent signal fails. ginext models signals as
    attributes, so an unknown signal surfaces as AttributeError rather than
    silently connecting nothing."""
    with pytest.raises(AttributeError, match="does_not_exist"):
        cancellable.connect("does-not-exist", lambda c: None)
