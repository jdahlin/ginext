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

"""Gtk-3.0 Gtk.Template compatibility coverage."""

from __future__ import annotations

import os
from typing import Any

import pytest


os.environ.setdefault("GINEXT_GTK_AUTO_INIT", "0")

pytestmark = [
    pytest.mark.xdist_group("gtk3"),
]


needs_display = pytest.mark.skipif(
    not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")),
    reason="GTK widget instantiation requires a real display",
)


@pytest.fixture(scope="module")
def Gtk() -> Any:
    from ginext import Gtk as _Gtk

    if _Gtk.get_major_version() != 3:
        pytest.skip("requires Gtk-3.0")
    return _Gtk


def _require_display(Gtk: Any) -> None:
    ok = Gtk.init_check([])
    if isinstance(ok, tuple):
        ok = ok[0]
    if not ok:
        pytest.skip("GTK widget instantiation requires a real display")


def _template_xml(type_name: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<interface>
  <template class="{type_name}" parent="GtkBox">
    <child>
      <object class="GtkLabel" id="hello_label">
        <property name="label">hello</property>
      </object>
    </child>
    <child>
      <object class="GtkButton" id="ok_button">
        <property name="label">OK</property>
      </object>
    </child>
  </template>
</interface>"""


@pytest.fixture
def TemplatedClass(Gtk: Any, unique_type_name: Any) -> Any:
    type_name = unique_type_name("GinextTestTemplate")

    @Gtk.Template(string=_template_xml(type_name))
    class GinextTestTemplate(Gtk.Box, type_name=type_name):  # type: ignore[misc,call-arg]
        hello_label = Gtk.Template.Child()
        ok_button = Gtk.Template.Child()

    return GinextTestTemplate


def test_template_module_attrs(Gtk: Any) -> None:
    assert callable(Gtk.Template)
    assert Gtk.Template.Child is not None


@needs_display
def test_template_decorator_works_without_gtype_name(Gtk: Any) -> None:
    _require_display(Gtk)

    @Gtk.Template(string=_template_xml("NoGType"))
    class NoGType(Gtk.Box):  # type: ignore[misc]
        hello_label = Gtk.Template.Child("hello_label")

    inst: Any = NoGType()
    assert inst.hello_label is not None


def test_template_decorator_requires_widget_subclass(Gtk: Any) -> None:
    with pytest.raises(TypeError, match="@Gtk.Template on Widgets"):

        @Gtk.Template(string=_template_xml("NotAWidget"))
        class NotAWidget:
            pass


def test_template_decorator_exclusive_sources(Gtk: Any) -> None:
    with pytest.raises(TypeError, match="exactly one"):
        Gtk.Template()
    with pytest.raises(TypeError, match="exactly one"):
        Gtk.Template(resource_path="/x", string="<interface/>")


def test_template_child_name_default(Gtk: Any) -> None:
    """Child() without an explicit name defaults to None; register_template
    fills in the attribute name when it iterates cls.__dict__."""
    child = Gtk.Template.Child()
    assert child.name is None
    assert child.internal is False


def test_template_child_explicit_name(Gtk: Any) -> None:
    child = Gtk.Template.Child("my_widget")
    assert child.name == "my_widget"


def test_template_decorator_stores_metadata_on_gimeta_extensions(
    TemplatedClass: Any,
) -> None:
    template = TemplatedClass.gimeta.extensions["Gtk"]["template"]
    assert template.children[0].template_name == "hello_label"
    assert template.children[0].attr_name == "hello_label"
    assert template.children[1].template_name == "ok_button"


def test_template_class_has_fresh_gtype(TemplatedClass: Any, Gtk: Any) -> None:
    from ginext import GObject

    gt = GObject.type_from_name(TemplatedClass.gimeta.type_name)
    assert gt == TemplatedClass.gimeta.gtype
    assert GObject.type_is_a(gt, Gtk.Box.gimeta.gtype)  # type_from_name returns int, accepted at runtime


@needs_display
def test_template_decorates_and_binds_children(TemplatedClass: Any, Gtk: Any) -> None:
    _require_display(Gtk)
    inst = TemplatedClass()
    assert inst.hello_label is not None
    assert "Label" in type(inst.hello_label).__name__
    assert inst.ok_button is not None
    assert "Button" in type(inst.ok_button).__name__


@needs_display
def test_template_children_bound_after_super_init(Gtk: Any) -> None:
    """Children must be accessible immediately after super().__init__()
    because Gtk.Template now runs from ginext's shared post-construction
    hook during the normal g_object_new()-style construction path."""
    _require_display(Gtk)
    seen: dict[str, Any] = {}

    ui = """<?xml version="1.0" encoding="UTF-8"?>
<interface>
  <template class="EarlyAccessTemplate3" parent="GtkBox">
    <child>
      <object class="GtkLabel" id="hello_label">
        <property name="label">hi</property>
      </object>
    </child>
  </template>
</interface>"""

    @Gtk.Template(string=ui)
    class EarlyAccess(Gtk.Box, type_name="EarlyAccessTemplate3"):  # type: ignore[misc,call-arg]
        hello_label = Gtk.Template.Child()

        def __init__(self) -> None:
            super().__init__()
            seen["label"] = self.hello_label

    inst: Any = EarlyAccess()
    assert seen["label"] is not None
    assert seen["label"] is inst.hello_label


@needs_display
def test_template_callback_wired_from_xml_signal(Gtk: Any) -> None:
    _require_display(Gtk)
    ui = """<?xml version="1.0" encoding="UTF-8"?>
<interface>
  <template class="CallbackWiring3" parent="GtkBox">
    <child>
      <object class="GtkButton" id="btn">
        <signal name="clicked" handler="on_clicked"/>
      </object>
    </child>
  </template>
</interface>"""
    fired: list[Any] = []

    @Gtk.Template(string=ui)
    class CallbackWiring(Gtk.Box, type_name="CallbackWiring3"):  # type: ignore[misc,call-arg]
        btn = Gtk.Template.Child()

        def on_clicked(self, *args: Any) -> None:
            fired.append(self)

    inst = CallbackWiring()
    inst.btn.clicked()
    assert fired == [inst]


@needs_display
def test_template_explicit_init_template(Gtk: Any) -> None:
    """init_template() stays explicitly callable, but automatic template
    setup already ran during construction so the second call is a no-op."""
    _require_display(Gtk)
    ui = """<?xml version="1.0" encoding="UTF-8"?>
<interface>
  <template class="ExplicitInitTemplate3" parent="GtkBox">
    <child>
      <object class="GtkLabel" id="lbl"/>
    </child>
  </template>
</interface>"""

    @Gtk.Template(string=ui)
    class ExplicitInit(Gtk.Box, type_name="ExplicitInitTemplate3"):  # type: ignore[misc,call-arg]
        lbl = Gtk.Template.Child()

        def __init__(self) -> None:
            super().__init__()
            self.init_template()

    inst: Any = ExplicitInit()
    assert inst.lbl is not None


@needs_display
def test_gnome_music_playlist_tile_shape(Gtk: Any, capfd: Any) -> None:
    """Gnome-music's PlaylistsView.current_playlist chain:

        sidebar.bind_model(model, factory)
        ...
        first_row = sidebar.get_row_at_index(0)
        sidebar.select_row(first_row)
        selected = sidebar.get_selected_row()
        selected.get_property_by_name("playlist")  # ← must still see the value the
                                 #   factory stored via __init__

    Before the tp_finalize save fix, `selected.get_property_by_name("playlist")` came
    back as None — the factory wrote it to the wrapper's __dict__,
    but Python's subtype_dealloc cleared that dict between the wrapper
    being GC'd and goi's tp_dealloc seeing it, so the qdata save
    read an empty dict and the next wrap restored nothing.
    """
    _require_display(Gtk)
    from ginext import Gio
    from ginext.gobject import gobjectclass as gobject

    class Playlist(gobject.GObject):
        title: str = gobject.Property(default="")

    @Gtk.Template(
        string="""<?xml version="1.0"?>
<interface>
  <template class="TileRoundTripTile" parent="GtkListBoxRow">
    <child><object class="GtkLabel" id="_label"/></child>
  </template>
</interface>"""
    )
    class Tile(Gtk.ListBoxRow, type_name="TileRoundTripTile"):  # type: ignore[misc,call-arg]
        _label = Gtk.Template.Child()
        playlist: "Playlist | None" = gobject.Property(default=None)

        def __init__(self, playlist: Any) -> None:
            super().__init__()
            self.playlist = playlist
            self._label.set_label(playlist.get_property_by_name("title"))

    def _factory(playlist: Any, _user_data: Any) -> Any:
        return Tile(playlist)

    sidebar = Gtk.ListBox()
    model = Gio.ListStore.new(item_type=Playlist)
    sidebar.bind_model(model, _factory, None, None)

    for name in ("MostPlayed", "Recent", "Favorites"):
        pl = Playlist()
        pl.title = name
        model.append(pl)  # type: ignore[arg-type]  # Playlist is a GObject subclass, accepted at runtime
    capfd.readouterr()

    first_row = sidebar.get_row_at_index(0)
    sidebar.select_row(first_row)
    selected = sidebar.get_selected_row()

    assert selected is first_row
    assert selected.get_property_by_name("playlist") is not None, (
        "get_selected_row().get_property_by_name('playlist') lost the factory __init__ write"
    )
    assert selected.get_property_by_name("playlist").get_property_by_name("title") == "MostPlayed"


def test_template_cannot_nest(Gtk: Any) -> None:
    with pytest.raises(TypeError, match="nest"):

        @Gtk.Template(string=_template_xml("NestOuter3"))
        class _Outer(Gtk.Box, type_name="NestOuter3"):  # type: ignore[misc,call-arg]
            pass

        @Gtk.Template(string=_template_xml("NestInner3"))
        class _Inner(_Outer, type_name="NestInner3"):  # type: ignore[call-arg]
            pass
