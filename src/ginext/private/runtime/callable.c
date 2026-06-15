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

#include "runtime/callable.h"
#include "marshal/enum.h"

#include <stdio.h>

void
pygi_describe_callable_shape (GICallableInfo *cb, int has_self, char *buf, size_t buf_size)
{
  if (buf_size == 0)
    return;
  const char *name = cb != NULL ? gi_base_info_get_name ((GIBaseInfo *)cb) : NULL;
  snprintf (buf, buf_size, "%s%s", has_self ? "self." : "", name != NULL ? name : "?");
}

PyObject *
pygi_unsupported_fallback_shape (const char *qualified_name, GICallableInfo *cb, const char *detail)
{
  char shape[128];
  pygi_describe_callable_shape (cb, 0, shape, sizeof (shape));
  PyErr_Format (PyExc_NotImplementedError,
                "%s: TODO ginext unsupported invoke shape %s%s%s",
                qualified_name != NULL ? qualified_name : "?",
                shape,
                detail != NULL ? ": " : "",
                detail != NULL ? detail : "");
  return NULL;
}

#include "GObject/hooks.h"
#include "runtime/module_funcs.h"

__attribute__ ((weak)) int
pygi_foreign_cairo_from_py (PyObject *value,
                            GIBaseInfo *iface,
                            GITransfer transfer,
                            GIArgument *out)
{
  (void)value;
  (void)iface;
  (void)transfer;
  (void)out;
  return 1;
}

__attribute__ ((weak)) PyObject *
pygi_foreign_cairo_to_py (GIBaseInfo *iface, gpointer pointer, GITransfer transfer)
{
  (void)iface;
  (void)pointer;
  (void)transfer;
  return NULL;
}

PyObject *
pygi_build_struct_class (const char *namespace_name, GIBaseInfo *info)
{
  if (namespace_name == NULL || info == NULL)
    Py_RETURN_NONE;
  const char *name = gi_base_info_get_name (info);
  if (name == NULL)
    Py_RETURN_NONE;

  PyObject *resolver = pygi_hook_last (pygi_hook_class_from_namespace_profile);
  if (resolver == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "class_from_namespace_profile hook not registered");
      return NULL;
    }
  PyObject *context = pygi_namespace_context ();
  if (context == NULL)
    return NULL;
  return PyObject_CallFunction (resolver, "Oss", context, namespace_name, name);
}
