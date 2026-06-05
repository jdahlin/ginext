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

"""GTK 3 only: UIManager and ActionGroup overlays."""

from __future__ import annotations

from typing import Any

from ginext import Gtk

overlay = Gtk.overlay

if Gtk.__version__[0] == 3:

    @overlay.method("UIManager")
    def add_ui_from_string(fn: Any, self: Any, buffer: Any) -> Any:
        if not isinstance(buffer, str):
            raise TypeError("buffer must be a string")
        return fn(self, buffer, len(buffer.encode("utf-8")))


if Gtk.__version__[0] == 3:

    @overlay.method("UIManager")
    def insert_action_group(fn: Any, self: Any, buffer: Any, length: int = -1) -> Any:
        return fn(self, buffer, length)


if Gtk.__version__[0] == 3:

    @overlay.method("ActionGroup")
    def add_actions(self: Any, entries: Any, user_data: Any = None) -> None:
        try:
            iter(entries)
        except TypeError as exc:
            raise TypeError("entries must be iterable") from exc

        def _process_action(
            name: Any,
            stock_id: Any = None,
            label: Any = None,
            accelerator: Any = None,
            tooltip: Any = None,
            callback: Any = None,
        ) -> None:
            action = Gtk.Action(
                name=name,
                label=label,
                tooltip=tooltip,
                stock_id=stock_id,
            )
            if callback is not None:
                if user_data is None:
                    action.connect("activate", callback)
                else:
                    action.connect("activate", callback, user_data)
            self.add_action_with_accel(action, accelerator)

        for entry in entries:
            _process_action(*entry)


if Gtk.__version__[0] == 3:

    @overlay.method("ActionGroup")
    def add_toggle_actions(self: Any, entries: Any, user_data: Any = None) -> None:
        try:
            iter(entries)
        except TypeError as exc:
            raise TypeError("entries must be iterable") from exc

        def _process_action(
            name: Any,
            stock_id: Any = None,
            label: Any = None,
            accelerator: Any = None,
            tooltip: Any = None,
            callback: Any = None,
            is_active: bool = False,
        ) -> None:
            action = Gtk.ToggleAction(
                name=name,
                label=label,
                tooltip=tooltip,
                stock_id=stock_id,
            )
            action.set_active(is_active)
            if callback is not None:
                if user_data is None:
                    action.connect("activate", callback)
                else:
                    action.connect("activate", callback, user_data)
            self.add_action_with_accel(action, accelerator)

        for entry in entries:
            _process_action(*entry)


if Gtk.__version__[0] == 3:

    @overlay.method("ActionGroup")
    def add_radio_actions(
        self: Any,
        entries: Any,
        value: Any = None,
        on_change: Any = None,
        user_data: Any = None,
    ) -> None:
        try:
            iter(entries)
        except TypeError as exc:
            raise TypeError("entries must be iterable") from exc

        first_action = None
        prev_action = None
        for entry in entries:
            name, stock_id, label, accelerator, tooltip, entry_value = (
                *entry,
                None,
                None,
                None,
                None,
                None,
            )[:6]
            kwargs: dict[str, Any] = {
                "name": name,
                "label": label,
                "tooltip": tooltip,
                "stock_id": stock_id,
            }
            if entry_value is not None:
                kwargs["value"] = entry_value
            action = Gtk.RadioAction(**kwargs)
            if prev_action is not None:
                action.join_group(prev_action)
            else:
                first_action = action
            prev_action = action
            self.add_action_with_accel(action, accelerator)
            if entry_value == value:
                action.set_active(True)

        if first_action is not None and on_change is not None:
            if user_data is None:
                first_action.connect("changed", on_change)
            else:
                first_action.connect("changed", on_change, user_data)
