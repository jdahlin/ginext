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

"""Gtk-4.0 template coverage ported from PyGObject tests."""

from __future__ import annotations

from typing import Any

import pytest

try:
    from ginext import Adw
except ImportError:
    # libadwaita (Adw) is not built on every platform (e.g. Windows/vcpkg).
    pytest.skip("Adw (libadwaita) namespace not available", allow_module_level=True)

from ginext import Gtk
from ginext_gtk._gtktemplate import TemplateRuntime


def test_template_api_is_exposed() -> None:
    assert callable(Gtk.Template)
    assert Gtk.Template.Child is not None


def test_template_metadata_is_stored_on_gimeta_extensions(
    require_gtk4_display: Any,
) -> None:
    del require_gtk4_display
    xml = """
<interface>
  <template class="TemplateMetaBox" parent="GtkBox">
    <child>
      <object class="GtkButton" id="button">
        <signal name="clicked" handler="on_button_clicked" />
      </object>
    </child>
  </template>
</interface>
"""

    @Gtk.Template(string=xml)
    class TemplateMetaBox(Gtk.Box):
        button: Gtk.Button

        def on_button_clicked(self, button: object) -> None:
            self.clicked_button = button

    template = TemplateMetaBox.gimeta.extensions["Gtk"]["template"]
    assert isinstance(template, TemplateRuntime)
    assert template.source.kind == "string"
    assert template.children[0].template_name == "button"
    assert template.children[0].attr_name == "button"
    assert template.signals[0].handler_name == "on_button_clicked"


def test_template_decorates_and_binds_children(require_gtk4_display: Any) -> None:
    del require_gtk4_display
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
        label: Gtk.Label

    box = TemplateBox()

    assert isinstance(box.label, Gtk.Label)
    assert box.label.get_label() == "hello"


def test_template_decorates_and_binds_implicitly_annotated_children(
    require_gtk4_display: Any,
) -> None:
    del require_gtk4_display
    xml = """
<interface>
  <template class="ImplicitTemplateBox" parent="GtkBox">
    <child>
      <object class="GtkLabel" id="label">
        <property name="label">hello</property>
      </object>
    </child>
  </template>
</interface>
"""

    @Gtk.Template(string=xml)
    class ImplicitTemplateBox(Gtk.Box):
        label: Gtk.Label

    box = ImplicitTemplateBox()

    assert isinstance(box.label, Gtk.Label)
    assert box.label.get_label() == "hello"


def test_template_signal_handler_wired_from_xml_signal(
    require_gtk4_display: Any,
) -> None:
    del require_gtk4_display
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
        button: Gtk.Button

        def on_button_clicked(self, button: object) -> None:
            self.clicked_button = button

    box = TemplateBox()
    box.button.clicked()

    assert box.clicked_button is box.button


def test_template_named_handler_from_xml_resolves_directly(
    require_gtk4_display: Any,
) -> None:
    del require_gtk4_display
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
        button: Gtk.Button

        def on_button_clicked(self, button: object) -> None:
            self.clicked_button = button

    box = NamedTemplateBox()
    box.button.clicked()

    assert box.clicked_button is box.button


def test_template_without_declared_signals_ignores_internal_gtk4_closures(
    require_gtk4_display: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    del require_gtk4_display
    xml = """
<interface>
  <requires lib="Adw" version="1.0"/>
  <template class="TemplatePreferencesDialog" parent="AdwPreferencesDialog">
    <child>
      <object class="AdwPreferencesPage">
        <child>
          <object class="AdwPreferencesGroup">
            <child>
              <object class="AdwActionRow" id="row">
                <property name="activatable-widget">scale</property>
                <child type="suffix">
                  <object class="GtkScale" id="scale">
                    <property name="orientation">horizontal</property>
                    <property name="draw-value">false</property>
                    <property name="adjustment">
                      <object class="GtkAdjustment">
                        <property name="lower">0</property>
                        <property name="upper">4</property>
                        <property name="step-increment">1</property>
                        <property name="page-increment">1</property>
                        <property name="value">2</property>
                      </object>
                    </property>
                  </object>
                </child>
              </object>
            </child>
          </object>
        </child>
      </object>
    </child>
  </template>
</interface>
"""

    @Gtk.Template(string=xml)
    class TemplatePreferencesDialog(Adw.PreferencesDialog):
        row: Adw.ActionRow
        scale: Gtk.Scale

    dialog = TemplatePreferencesDialog()
    captured = capsys.readouterr()

    assert isinstance(dialog.row, Adw.ActionRow)
    assert isinstance(dialog.scale, Gtk.Scale)
    assert captured.err == ""


def test_template_constructor_rejects_mixed_sources() -> None:
    with pytest.raises(TypeError, match="exactly one"):
        Gtk.Template(resource_path="/x", string="<interface/>")
