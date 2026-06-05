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

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from ginext import abi
from ginext.overlay import bootstrap, state

if TYPE_CHECKING:
    from pathlib import Path
    from ginext.namespace import Namespace


def test_overlay_path_env_registers_class_overlays(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ns_name = "OverlayBootstrapTest"
    overlay_dir = tmp_path / "_overlays"
    overlay_dir.mkdir()
    overlay_file = overlay_dir / f"{ns_name}.py"
    overlay_file.write_text(
        "\n".join(
            [
                "import ginext",
                f"overlay = ginext.{ns_name}.overlay",
                '@overlay.method("Expression", classmethod=True, name="coerce")',
                "def _coerce(fn, cls, value):",
                "    return value",
                "",
                "def apply_to_namespace(namespace):",
                "    return None",
                "",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("GINEXT_OVERLAY_PATH", str(overlay_dir))
    bootstrap.reset_for_test()
    state.class_method_overlays.pop((ns_name, "Expression"), None)

    namespace = cast(
        "Namespace",
        SimpleNamespace(__name__=ns_name, _profile=abi.NATIVE, _version="1.0"),
    )

    bootstrap.load_overlay_module_for(namespace)

    methods = state.class_method_overlays[(ns_name, "Expression")]
    assert "coerce" in methods
    assert methods["coerce"].as_classmethod is True
