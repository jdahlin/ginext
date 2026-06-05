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

"""Gtk-3.0 template coverage ported from PyGObject tests."""

from __future__ import annotations

from typing import Any

import pytest


def _require_display(Gtk: Any) -> None:
    ok = Gtk.init_check([])
    if isinstance(ok, tuple):
        ok = ok[0]
    if not ok:
        pytest.skip("GTK widget instantiation requires a real display")


def test_template_api_is_exposed() -> None:
    from ginext import Gtk

    assert callable(Gtk.Template)
    assert Gtk.Template.Child is not None


def test_template_decorates_and_binds_children() -> None:
    from ginext import Gtk

    _require_display(Gtk)
    xml = """
<interface>
  <template class="TemplateBox" parent="GtkBox">
    <child>
      <object class="GtkLabel" id="label">
        <property name="label">hello</property>
      </object>
    </child>
  </template>
</interface>
"""

    @Gtk.Template(string=xml)
    class TemplateBox(Gtk.Box):
        label = Gtk.Template.Child()

    box = TemplateBox()

    assert isinstance(box.label, Gtk.Label)
    assert box.label.get_label() == "hello"


def test_template_signal_handler_wired_from_xml_signal() -> None:
    from ginext import Gtk

    _require_display(Gtk)
    xml = """
<interface>
  <template class="TemplateBox" parent="GtkBox">
    <child>
      <object class="GtkButton" id="button">
        <signal name="clicked" handler="on_button_clicked" />
      </object>
    </child>
  </template>
</interface>
"""

    @Gtk.Template(string=xml)
    class TemplateBox(Gtk.Box):
        button = Gtk.Template.Child()

        def on_button_clicked(self, button: Any) -> None:
            self.clicked_button = button

    box = TemplateBox()
    box.button.clicked()

    assert box.clicked_button is box.button


def test_template_named_handler_from_xml_resolves_directly() -> None:
    from ginext import Gtk

    _require_display(Gtk)
    xml = """
<interface>
  <template class="NamedTemplateBox" parent="GtkBox">
    <child>
      <object class="GtkButton" id="button">
        <signal name="clicked" handler="on_button_clicked" />
      </object>
    </child>
  </template>
</interface>
"""

    @Gtk.Template(string=xml)
    class NamedTemplateBox(Gtk.Box):
        button = Gtk.Template.Child()

        def on_button_clicked(self, button: Any) -> None:
            self.clicked_button = button

    box = NamedTemplateBox()
    box.button.clicked()

    assert box.clicked_button is box.button


def test_template_constructor_rejects_mixed_sources() -> None:
    from ginext import Gtk

    with pytest.raises(TypeError, match="exactly one"):
        Gtk.Template(resource_path="/x", string="<interface/>")
