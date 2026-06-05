/* Copyright 2026 Johan Dahlin
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 */

#pragma once

#include <Python.h>

extern PyTypeObject *ginext_vfunc_wrapper_type;
extern PyType_Spec GinextVFuncWrapper_spec;

int
pygi_install_native_vfunc_attrs_for_class (PyObject *cls, PyObject *capsule);

PyObject *
py_install_native_vfunc_attrs (PyObject *module, PyObject *args);
