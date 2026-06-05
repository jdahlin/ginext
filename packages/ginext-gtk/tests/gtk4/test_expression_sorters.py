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

from __future__ import annotations

import itertools
import os
from typing import Any

import pytest

import ginext


_type_seq = itertools.count()


@pytest.fixture(scope="module", autouse=True)
def _setup() -> None:
    for ns, ver in (("Gtk", "4.0"), ("GObject", "2.0"), ("Gio", "2.0")):
        ginext.private.require_namespace(ns, ver)


@pytest.fixture
def Gtk(_setup: None) -> Any:
    from ginext import Gtk

    return Gtk


@pytest.fixture
def Gio(_setup: None) -> Any:
    from ginext import Gio

    return Gio


@pytest.fixture
def row_type(_setup: None) -> Any:
    from ginext import GObject

    suffix = f"{os.getpid()}_{next(_type_seq)}"

    class Row(GObject.Object, type_name=f"GoiExpressionSortRow{suffix}"):
        sort_bucket = GObject.Property(int, default=0)
        name = GObject.Property(str, default="")
        name_key = GObject.Property(str, default="")
        ext_key = GObject.Property(str, default="")
        size_key = GObject.Property(int, default=0)
        mtime_key = GObject.Property(int, default=0)
        attr_key = GObject.Property(str, default="")

    return Row


@pytest.fixture
def row_factory(row_type: Any) -> Any:
    def build(
        *,
        sort_bucket: int,
        name: str,
        name_key: str,
        ext_key: str = "",
        size_key: int = 0,
        mtime_key: int = 0,
        attr_key: str = "",
    ) -> Any:
        return row_type(
            sort_bucket=sort_bucket,
            name=name,
            name_key=name_key,
            ext_key=ext_key,
            size_key=size_key,
            mtime_key=mtime_key,
            attr_key=attr_key,
        )

    return build


@pytest.fixture
def sample_rows(row_factory: Any) -> list[Any]:
    return [
        row_factory(sort_bucket=0, name="..", name_key=".."),
        row_factory(sort_bucket=1, name="beta", name_key="beta"),
        row_factory(sort_bucket=1, name="alpha", name_key="alpha"),
        row_factory(
            sort_bucket=2,
            name="zeta.tar.gz",
            name_key="zeta.tar",
            ext_key="gz",
            size_key=300,
            mtime_key=1_700_000_000,
            attr_key="rwx-",
        ),
        row_factory(
            sort_bucket=2,
            name="alpha.txt",
            name_key="alpha",
            ext_key="txt",
            size_key=200,
            mtime_key=1_700_000_200,
            attr_key="r---",
        ),
        row_factory(
            sort_bucket=2,
            name="beta.py",
            name_key="beta",
            ext_key="py",
            size_key=100,
            mtime_key=1_700_000_100,
            attr_key="rw--",
        ),
    ]


def _string_sorter(Gtk: Any, row_type: Any, path: str) -> Any:
    sorter = Gtk.StringSorter.new(Gtk.PropertyExpression(path, this_type=row_type))
    sorter.set_ignore_case(True)
    return sorter


def _numeric_sorter(
    Gtk: Any, row_type: Any, path: str, *, descending: bool = False
) -> Any:
    sorter = Gtk.NumericSorter.new(Gtk.PropertyExpression(path, this_type=row_type))
    sorter.set_sort_order(
        Gtk.SortType.DESCENDING if descending else Gtk.SortType.ASCENDING
    )
    return sorter


def _multi_sorter(Gtk: Any, *sorters: Any) -> Any:
    sorter = Gtk.MultiSorter.new()
    for item in sorters:
        sorter.append(item)
    return sorter


def _sorted_names(
    Gtk: Any, Gio: Any, row_type: Any, rows: list[Any], sorter: Any
) -> list[str]:
    store = Gio.ListStore.new(row_type)
    for row in rows:
        store.append(row)
    model = Gtk.SortListModel.new(store, sorter)
    return [model.get_item(index).name for index in range(model.get_n_items())]


@pytest.mark.parametrize(
    ("sorter_name", "expected_names"),
    [
        pytest.param(
            "name",
            ["..", "alpha", "beta", "alpha.txt", "beta.py", "zeta.tar.gz"],
            id="name",
        ),
        pytest.param(
            "extension",
            ["..", "alpha", "beta", "zeta.tar.gz", "beta.py", "alpha.txt"],
            id="extension",
        ),
        pytest.param(
            "size",
            ["..", "alpha", "beta", "zeta.tar.gz", "alpha.txt", "beta.py"],
            id="size",
        ),
        pytest.param(
            "date",
            ["..", "alpha", "beta", "alpha.txt", "beta.py", "zeta.tar.gz"],
            id="date",
        ),
        pytest.param(
            "attr",
            ["..", "alpha", "beta", "alpha.txt", "beta.py", "zeta.tar.gz"],
            id="attr",
        ),
    ],
)
def test_expression_sorters_cover_commander_sort_policy(
    Gtk: Any,
    Gio: Any,
    row_type: Any,
    sample_rows: list[Any],
    sorter_name: str,
    expected_names: list[str],
) -> None:
    bucket = _numeric_sorter(Gtk, row_type, "sort_bucket")
    name = _string_sorter(Gtk, row_type, "name_key")
    sorters = {
        "name": _multi_sorter(Gtk, bucket, name),
        "extension": _multi_sorter(
            Gtk,
            bucket,
            _string_sorter(Gtk, row_type, "ext_key"),
            name,
        ),
        "size": _multi_sorter(
            Gtk,
            bucket,
            _numeric_sorter(Gtk, row_type, "size_key", descending=True),
            name,
        ),
        "date": _multi_sorter(
            Gtk,
            bucket,
            _numeric_sorter(Gtk, row_type, "mtime_key", descending=True),
            name,
        ),
        "attr": _multi_sorter(
            Gtk,
            bucket,
            _string_sorter(Gtk, row_type, "attr_key"),
            name,
        ),
    }
    assert (
        _sorted_names(Gtk, Gio, row_type, sample_rows, sorters[sorter_name])
        == expected_names
    )


@pytest.mark.parametrize("path", ["sort_bucket", "name_key", "ext_key"])
def test_expression_property_constructor_accepts_sort_property_paths(
    Gtk: Any, row_type: Any, path: str
) -> None:
    expression = Gtk.PropertyExpression(path, this_type=row_type)
    assert isinstance(expression, Gtk.PropertyExpression)


pytestmark = [pytest.mark.xdist_group("gtk")]
