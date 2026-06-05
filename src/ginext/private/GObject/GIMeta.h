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

/* GIMeta heap type: one per registered ginext GObject class. Carries the
 * GType, the resolved name, the parent Python class, and dicts mapping
 * Python attribute names to (GParamSpec pointer / prop_id). The pspecs
 * dict's values are GParamSpec pointers cast to Python ints — same
 * representation the previous dataclass version exposed.
 *
 * get_property/set_property methods walk type(obj).__mro__ themselves
 * to find inherited properties, so a B(A) instance can read/write A's
 * property even though B.gimeta.pspecs only lists B's own. */
typedef struct
{
  PyObject_HEAD GType gtype;
  PyObject *type_name; /* str */
  PyObject *parent; /* Python class or None */
  PyObject *pspecs; /* dict[str, int] — value is GParamSpec* */
  PyObject *prop_ids; /* dict[str, int] — 1-based prop_ids */
  PyObject *gi_info; /* GIBaseInfo capsule for imported classes or None */
  PyObject *namespace; /* Namespace object for imported classes or None */
  PyObject *method_owner_name; /* str qualified owner name or None */
  PyObject *method_infos; /* dict[str, (GIBaseInfo, has_self)] */
  PyObject *typelib_methods; /* dict[str, callable] */
  PyObject *signal_infos; /* dict[str, signal_info_or_descriptor] */
  PyObject *signal_method_backings; /* dict[str, callable] */
  PyObject *vfunc_infos; /* dict[str, vfunc_info] */
  PyObject *profile; /* ABIProfile or None */
  PyObject *extensions; /* dict[str, dict[str, object]] for toolkit metadata */
} GIMetaObject;

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
