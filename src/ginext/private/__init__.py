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

"""Re-export the C-implemented surface so callers can write
`ginext.private.GIMeta`, `ginext.private.PropertyDescriptor`, etc.

GIMeta is now a C heap type with `gtype` / `type_name` / `parent` /
`pspecs` / `prop_ids` properties plus `from_type_name` classmethod and
read-only metadata helpers. The previous dataclass wrapper has been retired;
there's no longer a dict→dataclass round-trip on Python subclass registration.
"""

from __future__ import annotations

import importlib.util
import importlib.machinery
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import types


def _load_gobject():
    try:
        from . import _gobject as module

        if hasattr(module, "GIMeta"):
            return module
    except ImportError:
        pass
    sys.modules.pop("ginext.private._gobject", None)

    package_dir = Path(__file__).resolve().parent
    ext_suffixes = tuple(importlib.machinery.EXTENSION_SUFFIXES)
    exact_suffix = ext_suffixes[0]

    def _candidate_key(path: Path) -> tuple[int, str]:
        return (0 if str(path).endswith(exact_suffix) else 1, str(path))

    candidates = sorted(
        (
            path
            for path in package_dir.glob("_gobject*")
            if str(path).endswith(ext_suffixes)
        ),
        key=_candidate_key,
    )
    if not candidates:
        search_dirs: list[Path] = []
        for entry in sys.path:
            if not entry:
                continue
            path = Path(entry)
            search_dirs.append(path)
            search_dirs.append(path / "ginext" / "private")
        for parent in package_dir.parents:
            search_dirs.append(parent / "src")
            search_dirs.append(parent / "src" / "ginext" / "private")
        project_root = package_dir.parents[2]
        search_dirs.extend(
            build_dir / "src"
            for build_dir in sorted((project_root / "build").glob("*"))
        )
        for search_dir in search_dirs:
            if not search_dir.is_dir():
                continue
            candidates.extend(
                sorted(
                    (
                        path
                        for path in search_dir.glob("_gobject*")
                        if str(path).endswith(ext_suffixes)
                    ),
                    key=_candidate_key,
                )
            )

    for candidate in candidates:
        spec = importlib.util.spec_from_file_location(
            "ginext.private._gobject", candidate
        )
        if spec is None or spec.loader is None:
            continue
        module: types.ModuleType = importlib.util.module_from_spec(spec)
        sys.modules["ginext.private._gobject"] = module
        spec.loader.exec_module(module)
        return module
    raise ImportError(
        "could not load ginext.private._gobject from the local build tree"
    )


_gobject = _load_gobject()

GIMeta = _gobject.GIMeta
# Created and bound by gobject.gobjectclass via init_gobject (it needs GObjectMeta).
GObject = None
GObjectMeta = _gobject.GObjectMeta
init_gobject = _gobject.init_gobject
register_gtype_pytype = _gobject.register_gtype_pytype
register_gobject_subclass = _gobject.register_gobject_subclass
gobject_get_property = _gobject.gobject_get_property
gobject_set_property = _gobject.gobject_set_property
GBoxed = _gobject.GBoxed
PropertyDescriptor = _gobject.PropertyDescriptor
build_callable_descriptor = _gobject.build_callable_descriptor
invoke = _gobject.invoke
class_struct_wrapper = _gobject.class_struct_wrapper
installed_versions = _gobject.installed_versions
invoke_callable_descriptor = _gobject.invoke_callable_descriptor
namespace_dir = _gobject.namespace_dir
namespace_find = _gobject.namespace_find
synthetic_callable = _gobject.synthetic_callable
callable_async_info = _gobject.callable_async_info
Fundamental = _gobject.Fundamental
record_setup_class = _gobject.record_setup_class
require_namespace = _gobject.require_namespace
gvalue_get_type = _gobject.gvalue_get_type
gvalue_get_gtype = _gobject.gvalue_get_gtype
gvalue_init_value = _gobject.gvalue_init_value
gvalue_unset_value = _gobject.gvalue_unset_value
gvalue_reset_value = _gobject.gvalue_reset_value
gvalue_get_value = _gobject.gvalue_get_value
gvalue_set_value = _gobject.gvalue_set_value
gvalue_set_data_int = _gobject.gvalue_set_data_int
gvalue_set_data_uint64 = _gobject.gvalue_set_data_uint64
gvalue_wrap_pointer = _gobject.gvalue_wrap_pointer


def register_converter(to_py, from_py):
    """Register both directions of a GValue<->Python converter for the
    fundamental GTypes ginext's core marshaller does not handle on its own.

    ``to_py(gtype, gvalue_ptr) -> object`` converts a GValue to Python;
    ``from_py(obj, gtype, gvalue_ptr) -> object`` fills an initialised GValue
    from a Python object (raise NotImplementedError for a type it does not
    cover). Either may be None.
    """
    if to_py is not None:
        register_hook("gvalue.to_py", to_py)
    if from_py is not None:
        register_hook("gvalue.from_py", from_py)
gstrv_get_type = _gobject.gstrv_get_type
glib_event_source_new = _gobject.glib_event_source_new
type_has_value_table = _gobject.type_has_value_table
register_static = _gobject.register_static
register_property_type_info = _gobject.register_property_type_info
register_signal = _gobject.register_signal
param_spec_info = _gobject.param_spec_info
param_spec_default_value = _gobject.param_spec_default_value
param_spec_numeric_info = _gobject.param_spec_numeric_info
register_hook = _gobject.register_hook
register_coercion = _gobject.register_coercion
