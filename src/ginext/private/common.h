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

/* Shared structs and macros used across the _gobject extension.
 *
 * The split is by "thing": one .c per heap-allocated Python type, one .c
 * per exported module function. This header collects the data the .c
 * files all need (ClassData/ClassState/InstancePrivate layouts, the GLib
 * vfunc forward decls, and the Py_AUTO_DECREF cleanup attribute).
 */
#ifndef GINEXT_COMMON_H
#define GINEXT_COMMON_H

#include <Python.h>
#include <glib-object.h>

/* Per-class state kept in the class struct's tail. ClassData owns the
 * pspecs array. ClassState is the bridge: it lives in the class struct
 * (at class_state_offset, appended to the class size) and points at the
 * ClassData allocated at registration plus the private-data offset GLib
 * uses to find each instance's GValue store. */
typedef struct
{
  guint n_props;
  GParamSpec **pspecs; /* n_props entries, each owned */
  size_t class_state_offset;
} ClassData;

typedef struct
{
  gint private_offset;
  ClassData *data;
  GType gtype;
  GObjectSetPropertyFunc parent_set_property;
  GObjectGetPropertyFunc parent_get_property;
} ClassState;

/* Flex array of GValues stored in each instance's private region. The
 * GValue at index `prop_id - 1` is the storage for the corresponding
 * pspec; instance_init pre-fills it from g_param_value_set_default. */
typedef struct _InstancePrivate
{
  GValue props[];
} InstancePrivate;

/* Cleanup attribute for stack-allocated PyObject pointers — works the way
 * g_autoptr does for GObject types. Used to keep error paths short. */
static inline void
py_xdecref_cleanup (PyObject **p)
{
  Py_XDECREF (*p);
}
#define Py_AUTO_DECREF __attribute__ ((cleanup (py_xdecref_cleanup)))

/* Forward decls for Object-class.c (vfuncs + private-space lookup). */
void
class_data_free (gpointer p);
ClassState *
class_state_from_type (GType gtype);
InstancePrivate *
instance_private_from_type (GTypeInstance *instance, GType gtype);
void
ginext_instance_init (GTypeInstance *instance, gpointer klass);
void
ginext_class_init (gpointer klass, gpointer user_data);

/* Shared GIRepository — fresh instance (not the default one) to work
 * around libgirepository 2.88's wrong-shared-libs bug across
 * namespaces. Lazily initialized; pthread-once protected. */
struct _GIRepository;
struct _GIRepository *
ginext_shared_repository (void);

#endif /* GINEXT_COMMON_H */
