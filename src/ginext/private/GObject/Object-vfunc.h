/* Copyright 2026 Johan Dahlin
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 */

#pragma once

#include <Python.h>
#include <glib-object.h>

int
ginext_gobject_validate_vfunc_overrides (PyObject *cls, PyObject *parent_cls);

int
ginext_gobject_install_vfunc_overrides (PyObject *cls, GType new_gt, PyObject *parent_cls);
