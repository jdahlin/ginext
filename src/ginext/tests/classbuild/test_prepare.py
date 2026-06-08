# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations


def test_public_metaclasses_expose_prepare() -> None:
    from ginext import GObject
    from ginext.fundamental import FundamentalMeta
    from ginext.gobject.gtype import GTypeMeta
    from ginext.record import RecordMeta

    assert type(GObject.Object).__prepare__("Widget", (GObject.Object,)) == {}
    assert GTypeMeta.__prepare__("MyGType", ()) == {}
    assert RecordMeta.__prepare__("MyRecord", ()) == {}
    assert FundamentalMeta.__prepare__("MyFundamental", ()) == {}
