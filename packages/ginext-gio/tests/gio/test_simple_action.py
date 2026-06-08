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

import os
import uuid

import pytest


def test_get_name_returns_python_str() -> None:
    from ginext import Gio

    action = Gio.SimpleAction.new("demo", None)

    assert action.get_name() == "demo"
    assert isinstance(action.get_name(), str)


def test_boxed_value_rejected_as_construct_property() -> None:
    pytest.importorskip("ginext")
    from ginext import Gio

    with pytest.raises(TypeError, match="parameter-type"):
        Gio.SimpleAction(parameter_type=object())  # type: ignore[arg-type]  # testing runtime rejection


def test_sequence_value_rejected_for_boxed_construct_property() -> None:
    pytest.importorskip("ginext")
    from ginext import Gio

    with pytest.raises(TypeError, match="parameter-type"):
        Gio.SimpleAction(parameter_type=[1, 2, 3])  # type: ignore[arg-type]  # testing runtime rejection


def test_add_action_entries_registers_stateless_action_and_callback() -> None:
    from ginext import Gio

    group = Gio.SimpleActionGroup()
    seen: list[tuple[str, object]] = []

    def on_activate(action: object, parameter: object) -> None:
        seen.append((action.get_name(), parameter))  # type: ignore[attr-defined]

    group.add_action_entries([("demo", on_activate)])  # type: ignore[list-item]  # ginext accepts tuples as ActionEntry at runtime
    action = group.lookup_action("demo")

    assert action is not None
    assert action.get_name() == "demo"

    action.activate(None)

    assert seen == [("demo", None)]
    assert len(group) == 1
    assert list(group) == ["demo"]
    assert "demo" in group
    assert "missing" not in group
    assert 1 not in group


def test_add_action_entries_registers_stateful_action_and_change_state() -> None:
    from ginext import GLib, Gio

    group = Gio.SimpleActionGroup()
    seen: list[bool] = []

    def on_change_state(action: object, value: object) -> None:
        assert isinstance(value, GLib.Variant)
        action.set_state(value)  # type: ignore[attr-defined]
        seen.append(value.unpack())

    group.add_action_entries([("toggle", None, None, "false", on_change_state)])  # type: ignore[list-item]  # ginext accepts tuples as ActionEntry at runtime
    action = group.lookup_action("toggle")

    assert action is not None
    state = action.get_state()
    assert state is not None
    if hasattr(state, "unpack"):
        assert state.unpack() is False
    else:
        assert state == "false"  # compatibility branch

    action.change_state(GLib.Variant("b", True))

    assert seen == [True]
    state = action.get_state()
    assert state is not None
    if hasattr(state, "unpack"):
        assert state.unpack() is True
    else:
        assert state == "true"  # compatibility branch


def test_add_action_entries_rejects_change_state_for_stateless_action() -> None:
    from ginext import Gio

    group = Gio.SimpleActionGroup()

    with pytest.raises(ValueError, match="Stateless action"):
        group.add_action_entries([("demo", None, None, None, lambda *_args: None)])  # type: ignore[list-item]  # ginext accepts tuples as ActionEntry at runtime


def test_gio_application_installs_gtk_action_metadata() -> None:
    from ginext import Gio, Gtk

    class App(Gio.Application):
        def __init__(self) -> None:
            super().__init__(
                application_id=f"org.ginext.GioAction{os.getpid()}.t{uuid.uuid4().hex}",
                flags=Gio.ApplicationFlags.NON_UNIQUE,
            )
            self.calls = 0

        @Gtk.action("preferences", ["<Primary>comma"])
        def _on_preferences(self) -> None:
            self.calls += 1

    app = App()
    action = app.lookup_action("preferences")

    assert action is not None
    action.activate(None)
    assert app.calls == 1
