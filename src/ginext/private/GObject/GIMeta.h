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

#ifndef GINEXT_GIMETA_H
#define GINEXT_GIMETA_H

#include "common.h"

typedef enum
{
  GINEXT_META_REGISTERED_TYPE = 1,
} GinextMetaKind;

typedef struct
{
  char *name;
  GParamSpec *pspec;
  guint prop_id;
} GinextPropertyMeta;

typedef struct
{
  PyObject_HEAD GinextMetaKind kind;
  GType gtype;
  PyObject *type_name; /* str */
  PyObject *gi_info; /* GIBaseInfo capsule for imported classes or None */
  PyObject *namespace; /* Namespace object for imported classes or None */
  PyObject *profile; /* ABIProfile or None */
} GIMetaObject;

/* Object/interface-like metadata. Properties are owned by a C table; pspecs
 * are borrowed from the registered class data or GObject class, not unreffed
 * by the meta object. Python-visible pspecs/prop_ids are snapshots. */
typedef struct
{
  GIMetaObject base;
  PyObject *parent; /* Python class or None */
  GinextPropertyMeta *properties;
  Py_ssize_t n_properties;
  PyObject *method_owner_name; /* str qualified owner name or None */
  PyObject *method_infos; /* dict[str, (GIBaseInfo, has_self)] */
  PyObject *typelib_methods; /* dict[str, callable] */
  PyObject *signal_infos; /* dict[str, signal_info_or_descriptor] */
  PyObject *signal_method_backings; /* dict[str, callable] */
  PyObject *vfunc_infos; /* dict[str, vfunc_info] */
  PyObject *extensions; /* dict[str, dict[str, object]] for toolkit metadata */
} GRegisteredTypeMetaObject;

extern PyTypeObject GIMetaType;

/* Constructor used by Object-register.c — steals refs to type_name, parent,
 * pspecs, prop_ids (caller owns them at the moment of call; on success
 * the GIMeta owns them, on failure the GIMeta dealloc cleans up). */
PyObject *
gimeta_new (GType gtype,
            PyObject *type_name,
            PyObject *parent,
            PyObject *pspecs,
            PyObject *prop_ids,
            PyObject *gi_info);

#endif /* GINEXT_GIMETA_H */
