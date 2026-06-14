/* Copyright 2026 Johan Dahlin
 *
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */

#ifndef GINEXT_GOBJECT_OBJECTMETA_H
#define GINEXT_GOBJECT_OBJECTMETA_H

#include "common.h"

/* Create the GObjectMeta metatype (a subclass of `type`) and add it to `module`
 * as "GObjectMeta". Returns a borrowed-from-module new reference, NULL on error.
 *
 * The metatype's runtime behaviour lives in Python: tp_getattro chains to
 * type.__getattribute__ and, on a miss, looks up
 * ginext.gobject.metaclass._gobjectmeta_getattr via sys.modules (lazy install of
 * introspected methods); __dir__ delegates to _gobjectmeta_dir the same way. */
PyObject *
pygi_create_gobjectmeta (PyObject *module);

#endif /* GINEXT_GOBJECT_OBJECTMETA_H */
