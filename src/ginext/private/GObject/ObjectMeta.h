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
 * The metatype's runtime behaviour lives in Python and is wired in via
 * pygi_gobjectmeta_set_hooks: tp_getattro chains to type.__getattribute__ and,
 * on a miss, calls the registered class-level __getattr__ body (lazy install of
 * introspected methods); __dir__ delegates to the registered body. */
PyObject *
pygi_create_gobjectmeta (PyObject *module);

/* Register the Python bodies the metatype slots delegate to. Either argument may
 * be NULL to leave the current value untouched (partial registration). */
void
pygi_gobjectmeta_set_hooks (PyObject *meta_getattr, PyObject *meta_dir);

#endif /* GINEXT_GOBJECT_OBJECTMETA_H */
