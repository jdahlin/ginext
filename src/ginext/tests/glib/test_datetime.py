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

"""GLib.DateTime/Date/TimeZone stay boxed GLib objects, but ginext additionally
accepts the matching stdlib datetime object wherever they are expected,
converting on demand."""

from __future__ import annotations

import datetime
import sys
import zoneinfo
from typing import Any

import pytest

# GLib.TimeZone on Windows does not resolve IANA zone names (e.g.
# "Europe/Stockholm") against a system tz database the way it does on
# Unix; g_time_zone_new_identifier falls back to UTC. This is a GLib
# platform limitation, not a ginext conversion bug.
_no_iana_timezone = pytest.mark.xfail(
    sys.platform == "win32",
    reason="GLib.TimeZone does not resolve IANA zone names on Windows",
    strict=True,
)


@pytest.fixture(scope="module")
def GLib() -> Any:
    from ginext import GLib

    return GLib


@pytest.fixture(scope="module")
def datetime_property_class(GLib: Any) -> Any:
    from ginext import GObject

    class DateTimeHolder(GObject.Object):
        dt = GObject.Property(type=GLib.DateTime)
        d = GObject.Property(type=GLib.Date)
        tz = GObject.Property(type=GLib.TimeZone)

    return DateTimeHolder


# --- DateTime -------------------------------------------------------------


def test_property_accepts_aware_datetime(datetime_property_class: Any, GLib: Any) -> None:
    obj = datetime_property_class()

    obj.dt = datetime.datetime(
        2026, 6, 3, 7, 30, 15, tzinfo=datetime.timezone(datetime.timedelta(hours=2))
    )

    assert isinstance(obj.dt, GLib.DateTime)
    assert (obj.dt.get_year(), obj.dt.get_month(), obj.dt.get_day_of_month()) == (
        2026,
        6,
        3,
    )
    assert obj.dt.get_utc_offset() == 2 * 3600 * 1_000_000


@_no_iana_timezone
def test_property_datetime_preserves_named_zone(
    datetime_property_class: Any,
) -> None:
    obj = datetime_property_class()

    obj.dt = datetime.datetime(2026, 1, 1, 12, tzinfo=zoneinfo.ZoneInfo("Europe/Stockholm"))

    assert obj.dt.get_timezone().get_identifier() == "Europe/Stockholm"


def test_property_accepts_glib_datetime(datetime_property_class: Any) -> None:
    obj = datetime_property_class()
    from ginext import GLib

    obj.dt = GLib.DateTime.new_utc(2000, 1, 1, 0, 0, 0)

    assert obj.dt.get_year() == 2000


def test_argument_accepts_datetime(GLib: Any) -> None:
    # A GI method taking a GDateTime arg accepts a stdlib datetime.
    dt = GLib.DateTime.new_utc(2026, 6, 3, 0, 0, 0)
    later = datetime.datetime(2026, 6, 4, tzinfo=datetime.timezone.utc)

    assert dt.difference(later) == -86400 * 1_000_000


# --- Date -----------------------------------------------------------------


def test_property_accepts_date(datetime_property_class: Any, GLib: Any) -> None:
    obj = datetime_property_class()

    obj.d = datetime.date(2026, 6, 3)

    assert isinstance(obj.d, GLib.Date)
    assert (obj.d.get_year(), int(obj.d.get_month()), obj.d.get_day()) == (2026, 6, 3)


# --- TimeZone -------------------------------------------------------------


@_no_iana_timezone
def test_property_accepts_zoneinfo(datetime_property_class: Any, GLib: Any) -> None:
    obj = datetime_property_class()

    obj.tz = zoneinfo.ZoneInfo("Europe/Stockholm")

    assert isinstance(obj.tz, GLib.TimeZone)
    assert obj.tz.get_identifier() == "Europe/Stockholm"


def test_property_accepts_fixed_offset(datetime_property_class: Any) -> None:
    obj = datetime_property_class()

    obj.tz = datetime.timezone(datetime.timedelta(hours=5))

    assert obj.tz.get_identifier() == "+05:00:00"


# --- None / rejection -----------------------------------------------------


def test_none_round_trips(datetime_property_class: Any) -> None:
    obj = datetime_property_class()

    obj.dt = datetime.datetime(2026, 1, 1)
    obj.dt = None

    assert obj.dt is None


def test_rejects_wrong_type(datetime_property_class: Any) -> None:
    obj = datetime_property_class()

    with pytest.raises(TypeError):
        obj.d = "nope"
