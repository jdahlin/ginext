# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import pytest

try:
    from ginext import Adw
except ImportError:
    pytest.skip("Adw (libadwaita) namespace not available", allow_module_level=True)


def test_sidebar_collection_dunders(require_gtk4_display: object) -> None:
    _ = require_gtk4_display

    sidebar = Adw.Sidebar()
    first = Adw.SidebarSection(title="First")
    second = Adw.SidebarSection(title="Second")

    sidebar.append(first)
    sidebar.append(second)

    assert len(sidebar) == 2
    assert list(sidebar) == [first, second]
    assert sidebar[0] is first
    assert sidebar[-1] is second
    assert sidebar[:] == [first, second]


def test_sidebar_section_collection_dunders(require_gtk4_display: object) -> None:
    _ = require_gtk4_display

    section = Adw.SidebarSection(title="Files")
    first = Adw.SidebarItem(title="One")
    second = Adw.SidebarItem(title="Two")

    section.append(first)
    section.append(second)

    assert len(section) == 2
    assert list(section) == [first, second]
    assert section[0] is first
    assert section[-1] is second
    assert section[:] == [first, second]
