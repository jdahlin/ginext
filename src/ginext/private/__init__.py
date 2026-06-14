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
`ginext.private.GIMeta`, `ginext.private.DeclaredProperty`, etc.

GIMeta is now a C heap type with `gtype` / `type_name` / `parent` /
`pspecs` / `prop_ids` properties plus `from_type_name` classmethod and
`get_property` / `set_property` methods. The previous dataclass wrapper
has been retired — there's no longer a dict→dataclass round-trip on
Python subclass registration.
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
GBoxed = _gobject.GBoxed
DeclaredProperty = _gobject.DeclaredProperty
build_callable_descriptor = _gobject.build_callable_descriptor
invoke = _gobject.invoke
class_struct_wrapper = _gobject.class_struct_wrapper
installed_versions = _gobject.installed_versions
preload_shared_library = _gobject.preload_shared_library
invoke_callable_descriptor = _gobject.invoke_callable_descriptor
invoke_stats = _gobject.invoke_stats
namespace_dir = _gobject.namespace_dir
namespace_find = _gobject.namespace_find
synthetic_callable = _gobject.synthetic_callable
callable_async_info = _gobject.callable_async_info
record_field_get = _gobject.record_field_get
record_field_set = _gobject.record_field_set
Fundamental = _gobject.Fundamental
record_ensure_size = _gobject.record_ensure_size
record_memory_get = _gobject.record_memory_get
record_memory_set = _gobject.record_memory_set
record_install_field_descriptors = _gobject.record_install_field_descriptors
record_field_names = _gobject.record_field_names
record_new = _gobject.record_new
register_boxed_class = _gobject.register_boxed_class
require_namespace = _gobject.require_namespace
reset_invoke_stats = _gobject.reset_invoke_stats
gvalue_get_type = _gobject.gvalue_get_type
gvalue_get_gtype = _gobject.gvalue_get_gtype
gvalue_init_value = _gobject.gvalue_init_value
gvalue_unset_value = _gobject.gvalue_unset_value
gvalue_reset_value = _gobject.gvalue_reset_value
gvalue_get_value = _gobject.gvalue_get_value
gvalue_set_value = _gobject.gvalue_set_value
gvalue_array_get_nth_type = _gobject.gvalue_array_get_nth_type
gvalue_set_to_py_fallback = _gobject.gvalue_set_to_py_fallback
gvalue_get_to_py_fallback = _gobject.gvalue_get_to_py_fallback
gvalue_set_from_py_converter = _gobject.gvalue_set_from_py_converter
gvalue_get_from_py_converter = _gobject.gvalue_get_from_py_converter
gvalue_set_data_int = _gobject.gvalue_set_data_int
gvalue_set_data_uint64 = _gobject.gvalue_set_data_uint64
gvalue_new_for_gtype = _gobject.gvalue_new_for_gtype
gvalue_wrap_pointer = _gobject.gvalue_wrap_pointer


def register_converter(to_py, from_py):
    """Register both directions of a GValue<->Python converter for the
    fundamental GTypes ginext's core marshaller does not handle on its own.

    ``to_py(gtype, gvalue_ptr) -> object`` converts a GValue to Python;
    ``from_py(obj, gtype, gvalue_ptr) -> object`` fills an initialised GValue
    from a Python object (raise NotImplementedError for a type it does not
    cover). Either may be None.
    """
    gvalue_set_to_py_fallback(to_py)
    gvalue_set_from_py_converter(from_py)


def get_converters():
    """Return the currently-installed ``(to_py, from_py)`` converters."""
    return gvalue_get_to_py_fallback(), gvalue_get_from_py_converter()
gstrv_get_type = _gobject.gstrv_get_type
gerror_get_type = _gobject.gerror_get_type
ensure_cairo_gobject_types = _gobject.ensure_cairo_gobject_types
glib_event_source_new = _gobject.glib_event_source_new
type_has_value_table = _gobject.type_has_value_table
register_static = _gobject.register_static
param_spec_info = _gobject.param_spec_info
param_spec_default_value = _gobject.param_spec_default_value
param_spec_numeric_info = _gobject.param_spec_numeric_info
register_hook = _gobject.register_hook
register_coercion = _gobject.register_coercion
