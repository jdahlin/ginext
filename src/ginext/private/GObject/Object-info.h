/* Copyright 2026 Johan Dahlin
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, see <http://www.gnu.org/licenses/>.
 */

#pragma once

#include "common.h"

#include <girepository/girepository.h>

int
pygi_object_info_from_py (PyObject *value, GIArgument *out);
PyObject *
pygi_gobject_wrapper_ref (GObject *object);
int
pygi_gobject_wrapper_store (GObject *object, PyObject *wrapper);
void
pygi_gobject_wrapper_clear (GObject *object);
GObject *
pygi_gobject_wrapper_pointer (PyObject *wrapper);
void
pygi_gobject_wrapper_bind_pointer (PyObject *wrapper, GObject *object);
void
pygi_gobject_wrapper_forget_pointer (PyObject *wrapper);
int
pygi_gobject_wrapper_local_bound (PyObject *wrapper, gboolean *bound);
int
pygi_gobject_wrapper_local_owns_ref (PyObject *wrapper, gboolean *owns_ref);
void
pygi_gobject_wrapper_local_set_owns_ref (PyObject *wrapper, gboolean owns_ref);
gboolean
pygi_gobject_wrapper_owns_ref (GObject *object);
void
pygi_gobject_wrapper_set_owns_ref (GObject *object, gboolean owns_ref);
int
pygi_gobject_wrapper_pin (GObject *object, PyObject *wrapper);
void
pygi_gobject_wrapper_unpin (GObject *object);
GObject *
pygi_gobject_get (PyObject *wrapper);
int
pygi_raise_gobject_type_error (const char *expected, PyObject *actual);
int
pygi_raise_gobject_type_error_for_gtype (GType expected_gtype, PyObject *actual);
PyObject *
pygi_gobject_to_py (GObject *object, GITransfer transfer);
PyObject *
pygi_gobject_to_py_as_gtype (GObject *object, GType wrapper_gtype, GITransfer transfer);
PyObject *
pygi_wrap_preallocated_gobject (GObject *object, GType wrapper_gtype);
PyObject *
pygi_gtype_value_to_py (GType gtype);
PyObject *
pygi_object_info_to_py (GIArgument *arg, GITransfer transfer);
PyObject *
py_construct_gobject (PyObject *module, PyObject *args);
PyObject *
pygi_signal_connect_full (PyObject *source_arg,
                          const char *signal_name,
                          PyObject *callback,
                          gboolean after,
                          gboolean once,
                          PyObject *owner_arg,
                          PyObject *signal_info_capsule,
                          int signal_arg_limit);
int
pygi_signal_is_action_full (PyObject *source_arg, const char *signal_name, gboolean *out_is_action);
PyObject *
pygi_signal_emit_full (PyObject *source_arg,
                       const char *signal_name,
                       PyObject *signal_info_capsule,
                       PyObject *emit_args);
PyObject *
pygi_signal_emit_with_gtypes_full (PyObject *source_arg,
                                   const char *signal_name,
                                   PyObject *arg_gtypes_tuple,
                                   PyObject *emit_args);
PyObject *
pygi_signal_add_emission_hook_full (GType gtype, const char *detailed_signal, PyObject *callback);
PyObject *
pygi_signal_remove_emission_hook_full (GType gtype, const char *detailed_signal, gulong hook_id);
PyObject *
pygi_gobject_get_property_by_name (PyObject *source_arg, const char *name);
int
pygi_gobject_set_property_on_object (GObject *source, const char *name, PyObject *py_value);
PyObject *
pygi_gobject_set_property_by_name (PyObject *source_arg, const char *name, PyObject *py_value);
