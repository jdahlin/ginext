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

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


# These tests need a process-global pygobject-compat + no-auto-init environment
# (GINEXT_FEATURES / GINEXT_GTK_AUTO_INIT). Those settings would poison the shared
# gtk4 worker, so run each test body in its own subprocess; the env is set in the
# parent fixture below so the child inherits it from the very start.
pytestmark = [pytest.mark.subprocess(timeout=30)]


@pytest.fixture(autouse=True)
def _compat_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    monkeypatch.setenv("GINEXT_FEATURES", "pygobject_compat")
    monkeypatch.setenv("GINEXT_GTK_AUTO_INIT", "0")
    yield


@pytest.mark.skipif(
    pytest.importorskip("ginext").defaults.resolve_version("Gtk") != "4.0",
    reason="gtk4 only",
)
def test_custom_sorter_compat_wraps_compare_args() -> None:
    from gi.repository import Gio, GObject, Gtk

    class Person(GObject.GObject):
        name: str = GObject.Property(default="")

        def __init__(self, name: str) -> None:
            super().__init__()
            self.set_property("name", name)

    def names_sort(name_a: Any, name_b: Any, user_data: Any) -> Any:
        assert isinstance(name_a, Person)
        assert isinstance(name_b, Person)
        assert user_data is None
        if name_a.get_property("name") < name_b.get_property("name"):
            return Gtk.Ordering.SMALLER
        if name_a.get_property("name") > name_b.get_property("name"):
            return Gtk.Ordering.LARGER
        return Gtk.Ordering.EQUAL

    model = Gio.ListStore.new(Person)
    sort_model = Gtk.SortListModel.new(model)
    sort_model.set_sorter(Gtk.CustomSorter.new(names_sort, None))

    john = Person("john")
    bob = Person("bob")
    model.append(john)
    model.append(bob)

    assert sort_model[0] == bob
    assert sort_model[1] == john


@pytest.mark.skipif(
    pytest.importorskip("ginext").defaults.resolve_version("Gtk") != "4.0",
    reason="gtk4 only",
)
def test_custom_sorter_compat_wraps_directory_list_file_infos(tmp_path: Path) -> None:
    from gi.repository import Gio, GLib, Gtk

    (tmp_path / "z-last.txt").write_text("z")
    (tmp_path / "a-first.txt").write_text("a")

    def compare(left: Any, right: Any, user_data: Any) -> Any:
        assert isinstance(left, Gio.FileInfo)
        assert isinstance(right, Gio.FileInfo)
        assert user_data is None
        left_name = left.get_name()
        right_name = right.get_name()
        if left_name < right_name:
            return Gtk.Ordering.SMALLER
        if left_name > right_name:
            return Gtk.Ordering.LARGER
        return Gtk.Ordering.EQUAL

    directory = Gio.File.new_for_path(str(tmp_path))
    model = Gtk.DirectoryList.new("standard::name,standard::type", directory)
    sort_model = Gtk.SortListModel.new(model)
    sort_model.set_sorter(Gtk.CustomSorter.new(compare, None))

    context = GLib.MainContext.default()
    while model.get_property("loading"):
        context.iteration(True)

    assert sort_model.get_n_items() == 2
    first = sort_model.get_item(0)
    second = sort_model.get_item(1)
    assert isinstance(first, Gio.FileInfo)
    assert isinstance(second, Gio.FileInfo)
    assert first.get_name() == "a-first.txt"
    assert second.get_name() == "z-last.txt"
