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

/* marshal/enum.c - int marshalling for enum/flags GI types.
 *
 * The heap-type builders for IntEnum / IntFlag moved to
 * GObject/Enum.{c,h} and GObject/Flags.{c,h}; this file is the
 * marshalling-only sliver: GIArgument <-> PyObject as plain ints. */
#include "marshal/enum.h"

#include <Python.h>
#include "GObject/hooks.h"

static Py_tss_t enum_namespace_context_key = Py_tss_NEEDS_INIT;

static int
ensure_enum_namespace_context_key (void)
{
  if (PyThread_tss_is_created (&enum_namespace_context_key))
    return 0;
  if (PyThread_tss_create (&enum_namespace_context_key) == 0)
    return 0;
  PyErr_SetString (PyExc_RuntimeError, "failed to create enum namespace context");
  return -1;
}

int
pygi_enum_push_namespace_context (PyObject *namespace, PyObject **previous_out)
{
  g_return_val_if_fail (previous_out != NULL, -1);
  if (ensure_enum_namespace_context_key () != 0)
    return -1;
  PyObject *previous = PyThread_tss_get (&enum_namespace_context_key);
  Py_XINCREF (namespace);
  if (PyThread_tss_set (&enum_namespace_context_key, namespace) != 0)
    {
      Py_XDECREF (namespace);
      PyErr_SetString (PyExc_RuntimeError, "failed to set enum namespace context");
      return -1;
    }
  *previous_out = previous;
  return 0;
}

void
pygi_enum_pop_namespace_context (PyObject *previous)
{
  PyObject *current = PyThread_tss_get (&enum_namespace_context_key);
  PyThread_tss_set (&enum_namespace_context_key, previous);
  Py_XDECREF (current);
}

PyObject *
pygi_namespace_context (void)
{
  if (ensure_enum_namespace_context_key () != 0)
    return NULL;
  PyObject *context = PyThread_tss_get (&enum_namespace_context_key);
  return context != NULL ? context : Py_None;
}

static PyObject *
enum_class_from_type_info (GITypeInfo *ti)
{
  g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (ti);
  if (iface == NULL)
    Py_RETURN_NONE;
  const char *namespace_name = gi_base_info_get_namespace (iface);
  const char *name = gi_base_info_get_name (iface);
  if (namespace_name == NULL || name == NULL)
    Py_RETURN_NONE;

  PyObject *context = pygi_namespace_context ();
  if (context == NULL)
    return NULL;

  PyObject *resolver = pygi_hook_last (pygi_hook_class_from_namespace_profile);
  if (resolver == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "class_from_namespace_profile hook not registered");
      return NULL;
    }
  return PyObject_CallFunction (resolver, "Oss", context, namespace_name, name);
}

static PyObject *
enum_value_to_py (GITypeInfo *ti, long value)
{
  PyObject *cls = enum_class_from_type_info (ti);
  if (cls == NULL)
    return NULL;
  if (cls == Py_None)
    {
      Py_DECREF (cls);
      return PyLong_FromLong (value);
    }
  PyObject *arg = PyLong_FromLong (value);
  if (arg == NULL)
    {
      Py_DECREF (cls);
      return NULL;
    }
  PyObject *obj = PyObject_CallOneArg (cls, arg);
  Py_DECREF (arg);
  Py_DECREF (cls);
  return obj;
}

int
pygi_enum_info_from_py (PyObject *h, GIArgument *out)
{
  g_return_val_if_fail (out != NULL, -1);
  /* Enum members are 32-bit but may be signed or unsigned (e.g. Regress's
     TestEnumUnsigned VALUE2 == 1<<31). PyLong_AsLong would overflow for
     unsigned members >= 2^31 on LLP64 (Windows, 32-bit long), so read a
     wider value and accept either a signed or unsigned 32-bit interpretation,
     storing the resulting bit pattern. */
  long long v = PyLong_AsLongLong (h);
  if (v == -1 && PyErr_Occurred ())
    {
      PyErr_Clear ();
      unsigned long long uv = PyLong_AsUnsignedLongLong (h);
      if (uv == (unsigned long long)-1 && PyErr_Occurred ())
        return -1;
      v = (long long)uv;
    }
  if (v < G_MININT32 || v > G_MAXUINT32)
    {
      PyErr_SetString (PyExc_OverflowError, "enum value out of 32-bit range");
      return -1;
    }
  out->v_int = (int)(uint32_t)(unsigned long long)v;
  return 0;
}

PyObject *
pygi_enum_info_to_py (GITypeInfo *ti, GIArgument *arg)
{
  g_return_val_if_fail (arg != NULL, NULL);
  return enum_value_to_py (ti, (long)arg->v_int);
}

int
pygi_flags_info_from_py (PyObject *h, GIArgument *out)
{
  g_return_val_if_fail (out != NULL, -1);
  unsigned long v = PyLong_AsUnsignedLong (h);
  if (v == (unsigned long)-1 && PyErr_Occurred ())
    return -1;
  if (v > 0xFFFFFFFFul)
    {
      PyErr_SetString (PyExc_OverflowError, "value out of uint32 range");
      return -1;
    }
  out->v_uint = (uint32_t)v;
  return 0;
}

PyObject *
pygi_flags_info_to_py (GITypeInfo *ti, GIArgument *arg)
{
  g_return_val_if_fail (arg != NULL, NULL);
  return enum_value_to_py (ti, (long)arg->v_uint);
}
