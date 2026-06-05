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

#include <girepository/girepository.h>
#include <Python.h>

GIRepository *
pygi_shared_repository (void);

int
pygi_register_property_type_info_for_gtype (GType gtype, const char *name, PyObject *capsule);

int
pygi_register_signal_for_gtype (GType gtype,
                                const char *signal_name,
                                GType return_gtype,
                                PyObject *arg_gtypes_tuple,
                                GSignalFlags signal_flags,
                                PyObject *accumulator_obj,
                                PyObject *accu_data_obj,
                                guint *out_signal_id);
