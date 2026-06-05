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

"""Boxed-struct field reads for NULL-terminated arrays of records.

Some boxed structs expose `Foo**` (NULL-terminated array of pointers
to other boxed structs) as a directly-readable field. The motivating
case is `Gio.DBusNodeInfo.interfaces` — `GDBusInterfaceInfo**` — which
showtime's mpris.py walks to enumerate D-Bus interfaces:

    for interface in Gio.DBusNodeInfo.new_for_xml(xml).interfaces:
        ...

The existing zero-terminated-array path in boxed_class_getattro only
handled `gchar**` (GStrv). For any other element type it fell through
to the primitive marshaller, which raised
`NotImplementedError: field interfaces has unsupported type tag 15`
(15 = GI_TYPE_TAG_ARRAY).

These tests pin the contract: each element of the NULL-terminated
array is wrapped as its boxed-class Python type.
"""

from __future__ import annotations

from typing import Any


_XML_TWO_IFACES = """<node>
  <interface name="org.example.Foo">
    <method name="Hello"/>
  </interface>
  <interface name="org.example.Bar">
    <property name="Volume" type="d" access="read"/>
  </interface>
</node>
"""

_XML_EMPTY = "<node/>"


def test_dbusnodeinfo_interfaces_returns_list_of_wrappers(Gio: Any) -> None:
    """Two interfaces in the XML → two DBusInterfaceInfo wrappers, in
    declaration order. Showtime's actual usage pattern."""
    node = Gio.DBusNodeInfo.new_for_xml(_XML_TWO_IFACES)
    ifaces = node.interfaces

    assert isinstance(ifaces, list)
    assert len(ifaces) == 2
    assert all(isinstance(i, Gio.DBusInterfaceInfo) for i in ifaces)
    assert [i.name for i in ifaces] == ["org.example.Foo", "org.example.Bar"]


def test_dbusnodeinfo_interfaces_empty_node(Gio: Any) -> None:
    """Empty <node/>. The field has no entries; record-pointer array
    fields surface as a list regardless of whether glib parked NULL
    or a 1-element sentinel in the struct — callers iterate
    unconditionally."""
    node = Gio.DBusNodeInfo.new_for_xml(_XML_EMPTY)
    assert node.interfaces == []


_XML_VOID_METHOD = """<node>
  <interface name="org.example.Foo">
    <method name="Ping"/>
  </interface>
</node>
"""


def test_interfaces_survive_parent_node_dropping(Gio: Any) -> None:
    """Wrappers minted for elements of a record-pointer array field
    point into memory owned by the parent boxed struct. If we don't
    keep the parent alive, the inner pointers dangle the moment the
    parent is dropped — and any field read on a wrapper crashes (or
    quietly reads junk).

    Showtime's repro is the iterator-on-temporary idiom:

        for interface in Gio.DBusNodeInfo.new_for_xml(XML).interfaces:
            for method in interface.methods:  # SIGSEGV
                ...

    Python drops the DBusNodeInfo after `.interfaces` returns; the
    list of DBusInterfaceInfo wrappers must each keep their parent
    pinned for the inner field reads to stay valid."""
    import gc

    ifaces = Gio.DBusNodeInfo.new_for_xml(_XML_TWO_IFACES).interfaces
    gc.collect()
    # Read a field on every wrapper — uses the parent's memory.
    names = [i.name for i in ifaces]
    assert names == ["org.example.Foo", "org.example.Bar"]
    # And the nested record-pointer array — exact showtime pattern.
    methods0 = ifaces[0].methods
    assert isinstance(methods0, list)


def test_dbusmethodinfo_args_are_iterable_when_empty(Gio: Any) -> None:
    """`<method name="Ping"/>` has no in args and no out args. glib's
    parser leaves `in_args` / `out_args` as NULL pointers (rather than
    a 1-element sentinel array). Showtime's mpris.py iterates over
    `method.out_args` unconditionally:

        "".join([arg.signature for arg in method.out_args])

    so the contract has to be that the field surfaces as an empty
    list, not None — pygobject's `for arg in None` would TypeError
    the same way. Wrapper-typed arrays are different from GStrv
    here: GStrv apps already handle the None case (parse_strv etc.),
    but introspection-record callers walk the list."""
    node = Gio.DBusNodeInfo.new_for_xml(_XML_VOID_METHOD)
    iface = node.interfaces[0]
    method = iface.methods[0]
    assert method.in_args == []
    assert method.out_args == []
