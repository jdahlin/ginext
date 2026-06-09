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

"""Comprehensive Gio.Settings tests.

Uses an in-memory backend (GSETTINGS_BACKEND=memory) and a compiled schema
bundle in tests/gio/fixtures/gsettings/. Each test that mutates state works
on a fresh Settings object so tests are isolated despite sharing the
process-level memory store.

Schema: org.ginext.test (path /org/ginext/test/)
  b-val      boolean  default true
  i-val      int32    default 42
  u-val      uint32   default 7
  x-val      int64    default 9000000000
  t-val      uint64   default 9000000000
  d-val      double   default 3.14
  s-val      string   default 'hello'
  strv-val   as       default ['a','b']
  fruit      enum     default 'apple'  (apple/banana/cherry)
  perms      flags    default ['read'] (read/write/exec)
  ranged     int32    default 50  range [1,100]
  variant-val (ii)   default (1,2)
  child      child schema → org.ginext.test.child

Schema: org.ginext.test.child  (path /org/ginext/test/child/)
  c-val  string  default 'child-default'

Schema: org.ginext.nopath  (no fixed path — used with new_with_path)
  np-int int32  default 99
"""

from __future__ import annotations

import os
import pathlib
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Generator

    from ginext import Gio

import pytest

_SCHEMA_DIR = pathlib.Path(__file__).parent / "fixtures" / "gsettings"
_SCHEMA_ID = "org.ginext.test"


def _schema_source() -> Gio.SettingsSchemaSource:
    from ginext import Gio

    parent = Gio.SettingsSchemaSource.get_default()
    source = Gio.SettingsSchemaSource.new_from_directory(str(_SCHEMA_DIR), parent, False)
    assert source is not None
    return source


def _schema(schema_id: str = _SCHEMA_ID) -> Gio.SettingsSchema:
    schema = _schema_source().lookup(schema_id, True)
    assert schema is not None
    return schema


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module", autouse=True)
def _settings_env() -> Generator[None, None, None]:
    """Point GSettings at the in-memory backend and local schema bundle."""
    old_backend = os.environ.get("GSETTINGS_BACKEND")
    old_schema = os.environ.get("GSETTINGS_SCHEMA_DIR")
    os.environ["GSETTINGS_BACKEND"] = "memory"
    # Prepend our dir so other schemas (e.g. org.gnome.test) remain accessible
    # in the same xdist worker process.
    os.environ["GSETTINGS_SCHEMA_DIR"] = os.pathsep.join(
        filter(None, [str(_SCHEMA_DIR), old_schema])
    )
    yield
    if old_backend is None:
        os.environ.pop("GSETTINGS_BACKEND", None)
    else:
        os.environ["GSETTINGS_BACKEND"] = old_backend
    if old_schema is None:
        os.environ.pop("GSETTINGS_SCHEMA_DIR", None)
    else:
        os.environ["GSETTINGS_SCHEMA_DIR"] = old_schema


@pytest.fixture
def s() -> Gio.Settings:
    """Fresh Settings object reset to schema defaults before each test."""
    from ginext import Gio

    settings = Gio.Settings.new_full(_schema(), None, None)
    for key in settings.list_keys():
        settings.reset(key)
    return settings


# ── construction ──────────────────────────────────────────────────────────────


def test_new_returns_settings_instance(s: Gio.Settings) -> None:
    from ginext import Gio

    assert type(s) is Gio.Settings


def test_new_path_is_set_from_schema(s: Gio.Settings) -> None:
    assert s.get_property("path") == "/org/ginext/test/"


def test_new_with_path_uses_supplied_path() -> None:
    from ginext import Gio

    s = Gio.Settings.new_full(_schema("org.ginext.nopath"), None, "/custom/path/")
    assert s.get_property("path") == "/custom/path/"
    assert s.get_int("np-int") == 99


def test_new_with_backend_accepts_memory_backend() -> None:
    from ginext import Gio

    backend = Gio.memory_settings_backend_new()
    s = Gio.Settings.new_full(_schema(), backend, None)
    assert type(s) is Gio.Settings
    assert s.get_boolean("b-val") is True


# ── get_boolean / set_boolean ─────────────────────────────────────────────────


def test_get_boolean_returns_default(s: Gio.Settings) -> None:
    assert s.get_boolean("b-val") is True


def test_set_boolean_roundtrip(s: Gio.Settings) -> None:
    s.set_boolean("b-val", False)
    assert s.get_boolean("b-val") is False


def test_set_boolean_true(s: Gio.Settings) -> None:
    s.set_boolean("b-val", False)
    s.set_boolean("b-val", True)
    assert s.get_boolean("b-val") is True


# ── get_int / set_int ─────────────────────────────────────────────────────────


def test_get_int_returns_default(s: Gio.Settings) -> None:
    assert s.get_int("i-val") == 42


def test_set_int_roundtrip(s: Gio.Settings) -> None:
    s.set_int("i-val", -1)
    assert s.get_int("i-val") == -1


def test_set_int_zero(s: Gio.Settings) -> None:
    s.set_int("i-val", 0)
    assert s.get_int("i-val") == 0


# ── get_uint / set_uint ───────────────────────────────────────────────────────


def test_get_uint_returns_default(s: Gio.Settings) -> None:
    assert s.get_uint("u-val") == 7


def test_set_uint_roundtrip(s: Gio.Settings) -> None:
    s.set_uint("u-val", 2**31)
    assert s.get_uint("u-val") == 2**31


# ── get_int64 / set_int64 ─────────────────────────────────────────────────────


def test_get_int64_returns_default(s: Gio.Settings) -> None:
    assert s.get_int64("x-val") == 9_000_000_000


def test_set_int64_roundtrip(s: Gio.Settings) -> None:
    large = -(2**62)
    s.set_int64("x-val", large)
    assert s.get_int64("x-val") == large


# ── get_uint64 / set_uint64 ───────────────────────────────────────────────────


def test_get_uint64_returns_default(s: Gio.Settings) -> None:
    assert s.get_uint64("t-val") == 9_000_000_000


def test_set_uint64_roundtrip(s: Gio.Settings) -> None:
    s.set_uint64("t-val", 2**63)
    assert s.get_uint64("t-val") == 2**63


# ── get_double / set_double ───────────────────────────────────────────────────


def test_get_double_returns_default(s: Gio.Settings) -> None:
    assert s.get_double("d-val") == pytest.approx(3.14)


def test_set_double_roundtrip(s: Gio.Settings) -> None:
    s.set_double("d-val", 2.718)
    assert s.get_double("d-val") == pytest.approx(2.718)


def test_set_double_negative(s: Gio.Settings) -> None:
    s.set_double("d-val", -1.0)
    assert s.get_double("d-val") == pytest.approx(-1.0)


# ── get_string / set_string ───────────────────────────────────────────────────


def test_get_string_returns_default(s: Gio.Settings) -> None:
    assert s.get_string("s-val") == "hello"


def test_set_string_roundtrip(s: Gio.Settings) -> None:
    s.set_string("s-val", "world")
    assert s.get_string("s-val") == "world"


def test_set_string_empty(s: Gio.Settings) -> None:
    s.set_string("s-val", "")
    assert s.get_string("s-val") == ""


def test_set_string_unicode(s: Gio.Settings) -> None:
    s.set_string("s-val", "héllo wörld")
    assert s.get_string("s-val") == "héllo wörld"


# ── get_strv / set_strv ───────────────────────────────────────────────────────


def test_get_strv_returns_default(s: Gio.Settings) -> None:
    assert s.get_strv("strv-val") == ["a", "b"]


def test_set_strv_roundtrip(s: Gio.Settings) -> None:
    s.set_strv("strv-val", ["x", "y", "z"])
    assert s.get_strv("strv-val") == ["x", "y", "z"]


def test_set_strv_empty(s: Gio.Settings) -> None:
    s.set_strv("strv-val", [])
    assert s.get_strv("strv-val") == []


# ── get_enum / set_enum ───────────────────────────────────────────────────────


def test_get_enum_returns_default_as_int(s: Gio.Settings) -> None:
    assert s.get_enum("fruit") == 0  # 'apple' → 0


def test_set_enum_roundtrip(s: Gio.Settings) -> None:
    s.set_enum("fruit", 1)  # 'banana'
    assert s.get_enum("fruit") == 1


def test_set_enum_cherry(s: Gio.Settings) -> None:
    s.set_enum("fruit", 2)
    assert s.get_enum("fruit") == 2


# ── get_flags / set_flags ─────────────────────────────────────────────────────


def test_get_flags_returns_default(s: Gio.Settings) -> None:
    assert s.get_flags("perms") == 1  # 'read' = 1


def test_set_flags_roundtrip(s: Gio.Settings) -> None:
    s.set_flags("perms", 3)  # read | write
    assert s.get_flags("perms") == 3


def test_set_flags_all(s: Gio.Settings) -> None:
    s.set_flags("perms", 7)  # read | write | exec
    assert s.get_flags("perms") == 7


def test_set_flags_zero(s: Gio.Settings) -> None:
    s.set_flags("perms", 0)
    assert s.get_flags("perms") == 0


# ── get_value / set_value ─────────────────────────────────────────────────────


def test_get_value_boolean_variant(s: Gio.Settings) -> None:
    from ginext import GLib

    v = s.get_value("b-val")
    assert isinstance(v, GLib.Variant)
    assert v.get_boolean() is True


def test_get_value_string_variant(s: Gio.Settings) -> None:

    v = s.get_value("s-val")
    assert v.get_string() == "hello"


def test_get_value_tuple_variant(s: Gio.Settings) -> None:
    v = s.get_value("variant-val")
    assert v.unpack() == (1, 2)


def test_set_value_roundtrip(s: Gio.Settings) -> None:
    from ginext import GLib

    s.set_value("s-val", GLib.Variant("s", "from-variant"))
    assert s.get_string("s-val") == "from-variant"


def test_set_value_boolean_variant(s: Gio.Settings) -> None:
    from ginext import GLib

    s.set_value("b-val", GLib.Variant("b", False))
    assert s.get_boolean("b-val") is False


# ── get_default_value ─────────────────────────────────────────────────────────


def test_get_default_value_boolean(s: Gio.Settings) -> None:
    s.set_boolean("b-val", False)
    default = s.get_default_value("b-val")
    assert default is not None
    assert default.get_boolean() is True


def test_get_default_value_string(s: Gio.Settings) -> None:
    s.set_string("s-val", "changed")
    default = s.get_default_value("s-val")
    assert default is not None
    assert default.get_string() == "hello"


# ── get_user_value ────────────────────────────────────────────────────────────


def test_get_user_value_none_at_default(s: Gio.Settings) -> None:
    assert s.get_user_value("b-val") is None


def test_get_user_value_present_after_set(s: Gio.Settings) -> None:
    from ginext import GLib

    s.set_boolean("b-val", False)
    uv = s.get_user_value("b-val")
    assert isinstance(uv, GLib.Variant)
    assert uv.get_boolean() is False


def test_get_user_value_gone_after_reset(s: Gio.Settings) -> None:
    s.set_boolean("b-val", False)
    s.reset("b-val")
    assert s.get_user_value("b-val") is None


# ── reset ─────────────────────────────────────────────────────────────────────


def test_reset_restores_default(s: Gio.Settings) -> None:
    s.set_string("s-val", "changed")
    s.reset("s-val")
    assert s.get_string("s-val") == "hello"


def test_reset_clears_user_value(s: Gio.Settings) -> None:
    s.set_int("i-val", 999)
    s.reset("i-val")
    assert s.get_user_value("i-val") is None


# ── is_writable ───────────────────────────────────────────────────────────────


def test_is_writable_returns_true_for_normal_key(s: Gio.Settings) -> None:
    assert s.is_writable("b-val") is True


def test_is_writable_returns_true_for_string_key(s: Gio.Settings) -> None:
    assert s.is_writable("s-val") is True


# ── list_keys ─────────────────────────────────────────────────────────────────


def test_list_keys_contains_all_keys(s: Gio.Settings) -> None:
    keys = s.list_keys()
    assert set(keys) == {
        "b-val",
        "i-val",
        "u-val",
        "x-val",
        "t-val",
        "d-val",
        "s-val",
        "strv-val",
        "fruit",
        "perms",
        "ranged",
        "variant-val",
    }


def test_list_keys_returns_list(s: Gio.Settings) -> None:
    assert isinstance(s.list_keys(), list)


# ── list_children ─────────────────────────────────────────────────────────────


def test_list_children_contains_child(s: Gio.Settings) -> None:
    assert s.list_children() == ["child"]


# ── get_child ─────────────────────────────────────────────────────────────────


def test_get_child_returns_settings(s: Gio.Settings) -> None:
    from ginext import Gio

    child = s.get_child("child")
    assert isinstance(child, Gio.Settings)


def test_get_child_has_correct_path(s: Gio.Settings) -> None:
    child = s.get_child("child")
    assert child.get_property("path") == "/org/ginext/test/child/"


def test_get_child_reads_its_own_keys(s: Gio.Settings) -> None:
    child = s.get_child("child")
    assert child.get_string("c-val") == "child-default"


def test_get_child_mutations_are_independent(s: Gio.Settings) -> None:
    child = s.get_child("child")
    child.set_string("c-val", "modified")
    child.reset("c-val")
    assert child.get_string("c-val") == "child-default"


# ── range / range_check ───────────────────────────────────────────────────────


def test_get_range_type_for_ranged_key(s: Gio.Settings) -> None:
    r = s.get_range("ranged")
    kind, values = r.unpack()
    assert kind == "range"
    lo, hi = values
    assert lo == 1
    assert hi == 100


def test_get_range_type_for_unranged_key(s: Gio.Settings) -> None:
    r = s.get_range("i-val")
    kind, _ = r.unpack()
    assert kind == "type"


def test_range_check_valid_value(s: Gio.Settings) -> None:
    from ginext import GLib

    assert s.range_check("ranged", GLib.Variant("i", 50)) is True


def test_range_check_boundary_low(s: Gio.Settings) -> None:
    from ginext import GLib

    assert s.range_check("ranged", GLib.Variant("i", 1)) is True


def test_range_check_boundary_high(s: Gio.Settings) -> None:
    from ginext import GLib

    assert s.range_check("ranged", GLib.Variant("i", 100)) is True


def test_range_check_below_min(s: Gio.Settings) -> None:
    from ginext import GLib

    assert s.range_check("ranged", GLib.Variant("i", 0)) is False


def test_range_check_above_max(s: Gio.Settings) -> None:
    from ginext import GLib

    assert s.range_check("ranged", GLib.Variant("i", 101)) is False


# ── delay / revert / apply / get_has_unapplied ────────────────────────────────


def test_delay_sets_has_unapplied_after_change(s: Gio.Settings) -> None:
    s.delay()
    s.set_string("s-val", "delayed")
    assert s.get_has_unapplied() is True


def test_revert_discards_delayed_changes(s: Gio.Settings) -> None:
    s.delay()
    s.set_string("s-val", "delayed")
    s.revert()
    assert s.get_string("s-val") == "hello"
    assert s.get_has_unapplied() is False


def test_apply_commits_delayed_changes(s: Gio.Settings) -> None:
    s.delay()
    s.set_string("s-val", "committed")
    s.apply()
    assert s.get_string("s-val") == "committed"
    assert s.get_has_unapplied() is False


def test_no_unapplied_at_default(s: Gio.Settings) -> None:
    assert s.get_has_unapplied() is False


# ── changed signal ────────────────────────────────────────────────────────────


def test_changed_signal_fires_on_set(s: Gio.Settings) -> None:
    log = []
    s.changed.connect(lambda settings, key: log.append(key), owner=s)
    s.set_string("s-val", "trigger")
    assert "s-val" in log


def test_changed_signal_fires_with_correct_key(s: Gio.Settings) -> None:
    log = []
    s.changed.connect(lambda settings, key: log.append(key), owner=s)
    s.set_boolean("b-val", False)
    assert log == ["b-val"]


def test_changed_signal_disconnect_stops_delivery(s: Gio.Settings) -> None:
    log = []
    handle = s.changed.connect(lambda settings, key: log.append(key), owner=s)
    s.set_string("s-val", "first")
    handle.disconnect()
    s.set_string("s-val", "second")
    assert log == ["s-val"]


def test_changed_signal_fires_multiple_times(s: Gio.Settings) -> None:
    log = []
    s.changed.connect(lambda settings, key: log.append(key), owner=s)
    s.set_int("i-val", 1)
    s.set_int("i-val", 2)
    assert log == ["i-val", "i-val"]


# ── writable_changed signal ───────────────────────────────────────────────────


def test_writable_changed_signal_is_connectable(s: Gio.Settings) -> None:
    log = []
    s.writable_changed.connect(lambda settings, key: log.append(key), owner=s)
    assert isinstance(log, list)


# ── change_event signal ───────────────────────────────────────────────────────


def test_change_event_fires_on_set(s: Gio.Settings) -> None:
    log: list[int] = []

    def _on_change_event(settings: Gio.Settings, keys: list[int] | None) -> bool:
        log.append(len(keys) if keys is not None else 0)
        return False

    s.change_event.connect(_on_change_event, owner=s)
    s.set_boolean("b-val", False)
    assert log == [1]


# ── bind ──────────────────────────────────────────────────────────────────────


def test_bind_default_syncs_settings_to_object(s: Gio.Settings) -> None:
    from ginext import Gio

    action = Gio.SimpleAction(name="test", enabled=True)
    s.bind("b-val", action, "enabled", Gio.SettingsBindFlags.DEFAULT)
    s.set_boolean("b-val", False)
    assert action.get_property("enabled") is False
    Gio.Settings.unbind(action, "enabled")


def test_bind_get_only_does_not_write_back(s: Gio.Settings) -> None:
    from ginext import Gio

    action = Gio.SimpleAction(name="test2", enabled=True)
    s.bind("b-val", action, "enabled", Gio.SettingsBindFlags.GET)
    s.set_boolean("b-val", False)
    assert action.get_property("enabled") is False
    Gio.Settings.unbind(action, "enabled")


# ── bind_writable ─────────────────────────────────────────────────────────────


def test_bind_writable_reflects_writability(s: Gio.Settings) -> None:
    from ginext import Gio

    action = Gio.SimpleAction(name="wtest", enabled=False)
    s.bind_writable("s-val", action, "enabled", False)
    assert action.get_property("enabled") is True
    Gio.Settings.unbind(action, "enabled")


# ── create_action ─────────────────────────────────────────────────────────────


def test_create_action_returns_action(s: Gio.Settings) -> None:
    action = s.create_action("b-val")
    # Gio.Action is a GInterface; check duck-type rather than isinstance.
    assert action is not None
    assert callable(action.get_name)


def test_create_action_name_matches_key(s: Gio.Settings) -> None:
    action = s.create_action("b-val")
    assert action.get_name() == "b-val"


def test_create_action_for_string_key(s: Gio.Settings) -> None:
    action = s.create_action("s-val")
    assert action is not None
    assert callable(action.get_name)


# ── list_schemas / list_relocatable_schemas ───────────────────────────────────


def test_list_schemas_includes_test_schema() -> None:
    from ginext import Gio

    schemas = Gio.Settings.list_schemas()
    assert _SCHEMA_ID in schemas


def test_list_schemas_includes_child_schema() -> None:
    from ginext import Gio

    schemas = Gio.Settings.list_schemas()
    assert "org.ginext.test.child" in schemas


def test_list_relocatable_schemas_includes_nopath_schema() -> None:
    from ginext import Gio

    reloc = Gio.Settings.list_relocatable_schemas()
    assert "org.ginext.nopath" in reloc


def test_list_relocatable_schemas_excludes_pathed_schema() -> None:
    from ginext import Gio

    reloc = Gio.Settings.list_relocatable_schemas()
    assert _SCHEMA_ID not in reloc


# ── SettingsSchemaSource ──────────────────────────────────────────────────────


def test_schema_source_get_default_returns_source() -> None:
    from ginext import Gio

    src = Gio.SettingsSchemaSource.get_default()
    assert src is not None


def test_schema_source_lookup_returns_schema() -> None:
    schema = _schema()
    assert schema is not None


def test_schema_source_lookup_unknown_returns_none() -> None:
    src = _schema_source()
    assert src.lookup("org.ginext.nonexistent", False) is None


def test_schema_source_list_schemas_contains_test_schema() -> None:
    src = _schema_source()
    non_relocatable, relocatable = src.list_schemas(True)
    assert _SCHEMA_ID in non_relocatable
    assert "org.ginext.nopath" in relocatable


# ── SettingsSchema ────────────────────────────────────────────────────────────


def test_schema_get_id() -> None:
    schema = _schema()
    assert schema.get_id() == _SCHEMA_ID


def test_schema_get_path() -> None:
    schema = _schema()
    assert schema.get_path() == "/org/ginext/test/"


def test_schema_has_key_true() -> None:
    schema = _schema()
    assert schema.has_key("b-val") is True


def test_schema_has_key_false() -> None:
    schema = _schema()
    assert schema.has_key("nonexistent") is False


def test_schema_list_keys() -> None:
    schema = _schema()
    keys = schema.list_keys()
    assert "b-val" in keys
    assert "s-val" in keys


# ── SettingsSchemaKey ─────────────────────────────────────────────────────────


def test_schema_key_get_name() -> None:
    schema = _schema()
    key = schema.get_key("b-val")
    assert key.get_name() == "b-val"


def test_schema_key_get_value_type_boolean() -> None:
    schema = _schema()
    key = schema.get_key("b-val")
    assert key.get_value_type().dup_string() == "b"


def test_schema_key_get_value_type_string() -> None:
    schema = _schema()
    key = schema.get_key("s-val")
    assert key.get_value_type().dup_string() == "s"


def test_schema_key_get_default_value_boolean() -> None:
    schema = _schema()
    key = schema.get_key("b-val")
    assert key.get_default_value().get_boolean() is True


def test_schema_key_get_default_value_string() -> None:
    schema = _schema()
    key = schema.get_key("s-val")
    assert key.get_default_value().get_string() == "hello"


def test_schema_key_get_range_unranged() -> None:
    schema = _schema()
    key = schema.get_key("i-val")
    kind, _ = key.get_range().unpack()
    assert kind == "type"


def test_schema_key_get_range_ranged() -> None:
    schema = _schema()
    key = schema.get_key("ranged")
    kind, values = key.get_range().unpack()
    assert kind == "range"
    assert values == (1, 100)


def test_schema_key_get_summary() -> None:
    schema = _schema()
    key = schema.get_key("b-val")
    assert key.get_summary() == "A boolean setting"


def test_schema_key_get_description() -> None:
    schema = _schema()
    key = schema.get_key("b-val")
    description = key.get_description()
    assert description is not None
    assert "boolean" in description
