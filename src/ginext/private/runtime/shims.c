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

/* This file has been split into:
 *   GObject/Value.c           — GValue Python wrappers
 *   GObject/Object-property.c — GObject property get/set helpers
 *   GObject/Boxed.c           — GLib.Boxed base type, record descriptors
 *   GObject/Closure-callback.c — FFI callback closures
 *   GObject/ParamSpec-make.c  — GParamSpec wrappers
 *   runtime/callable.c        — cairo stubs, pygi_build_struct_class
 *   GIRepository/Repository.c — pygi_shared_repository, pygi_load_array_element
 */

#include "GObject/hooks.h"

PyTypeObject *pygi_gboxed_base_type = NULL;
PyTypeObject *pygi_gobject_type = NULL;
