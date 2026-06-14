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

/* gvalue.c - GObject GValue marshaling (Python <-> GValue). */
#include "marshal/gvalue.h"
#include "GObject/hooks.h"
#include "cairo/foreign.h"
#include "marshal/enum.h"
#include "marshal/pygi-value.h"
#include "runtime/class-registry.h"
#include "GObject/Boxed.h"
#include "GObject/Object.h"
#include "GObject/Object-info.h"
#include "GObject/ParamSpec.h"
#include "GObject/Value.h"
#include "marshal/marshal.h"
#include "marshal/string.h"
#include "runtime/module_funcs.h"
#include "GObject/Object-class.h"
#include "runtime/type-info.h"
#include "GLib/Variant.h"
#include "GLib/Error.h"
#include "GObject/coercions.h"
#include "GLib/DateTime.h"
#include "gimeta-helpers.h"

#include <string.h>

#if GLIB_CHECK_VERSION(2, 32, 0)
G_GNUC_BEGIN_IGNORE_DEPRECATIONS
#include <gobject/gvaluearray.h>
G_GNUC_END_IGNORE_DEPRECATIONS
#endif

static int
pyobject_get_pygi_gtype (PyObject *obj, GType *out);

static PyObject *
resolve_boxed_pytype_from_context (GType gtype); /* forward decl */

static int
gvalue_hook_not_handled (void)
{
  if (PyErr_ExceptionMatches (PyExc_AttributeError)
      || PyErr_ExceptionMatches (PyExc_NotImplementedError))
    {
      PyErr_Clear ();
      return 1;
    }
  return 0;
}

static PyObject *
gvalue_call_to_py_hook (GType gtype, GValue *value)
{
  PyObject *list = pygi_hook_gvalue_to_py;
  if (list == NULL || !PyList_Check (list))
    {
      PyErr_SetString (PyExc_AttributeError, "no GValue to-Python hook registered");
      return NULL;
    }

  PyObject *py_gtype = PyLong_FromUnsignedLongLong ((unsigned long long)gtype);
  PyObject *py_ptr = PyLong_FromVoidPtr ((void *)value);
  if (py_gtype == NULL || py_ptr == NULL)
    {
      Py_XDECREF (py_gtype);
      Py_XDECREF (py_ptr);
      return NULL;
    }

  Py_ssize_t n = PyList_GET_SIZE (list);
  for (Py_ssize_t i = n - 1; i >= 0; i--)
    {
      PyObject *handler = PyList_GET_ITEM (list, i);
      PyObject *result = PyObject_CallFunctionObjArgs (handler, py_gtype, py_ptr, NULL);
      if (result != NULL)
        {
          Py_DECREF (py_gtype);
          Py_DECREF (py_ptr);
          return result;
        }
      if (!gvalue_hook_not_handled ())
        {
          Py_DECREF (py_gtype);
          Py_DECREF (py_ptr);
          return NULL;
        }
    }

  Py_DECREF (py_gtype);
  Py_DECREF (py_ptr);
  PyErr_SetString (PyExc_AttributeError, "no GValue to-Python hook handled the type");
  return NULL;
}

static int
gvalue_call_from_py_hook (PyObject *obj, GType type, GValue *value)
{
  PyObject *list = pygi_hook_gvalue_from_py;
  if (list == NULL || !PyList_Check (list))
    return 1;

  PyObject *py_gtype = PyLong_FromUnsignedLongLong ((unsigned long long)type);
  PyObject *py_ptr = PyLong_FromVoidPtr ((void *)value);
  if (py_gtype == NULL || py_ptr == NULL)
    {
      Py_XDECREF (py_gtype);
      Py_XDECREF (py_ptr);
      return -1;
    }

  Py_ssize_t n = PyList_GET_SIZE (list);
  for (Py_ssize_t i = n - 1; i >= 0; i--)
    {
      PyObject *handler = PyList_GET_ITEM (list, i);
      PyObject *result = PyObject_CallFunctionObjArgs (handler, obj, py_gtype, py_ptr, NULL);
      if (result != NULL)
        {
          Py_DECREF (result);
          Py_DECREF (py_gtype);
          Py_DECREF (py_ptr);
          return 0;
        }
      if (!gvalue_hook_not_handled ())
        {
          Py_DECREF (py_gtype);
          Py_DECREF (py_ptr);
          return -1;
        }
    }

  Py_DECREF (py_gtype);
  Py_DECREF (py_ptr);
  return 1;
}

/* Allocate a zeroed GValue initialised to gtype and wrap it as a Python
 * GObject.Value boxed object. The caller receives a strong reference;
 * the GValue's memory is freed (after g_value_unset) when the wrapper is
 * garbage-collected. Raises ValueError if gtype is not a value type, or
 * RuntimeError if the GObject.Value Python class is not yet registered. */
PyObject *
pygi_gvalue_new_for_gtype (GType gtype)
{
  if (!G_TYPE_IS_VALUE_TYPE (gtype))
    {
      PyErr_SetString (PyExc_ValueError, "GType is not a value type");
      return NULL;
    }
  PyObject *cls = pygi_class_registry_get_pytype_for_gtype (G_TYPE_VALUE);
  PyObject *owned_cls = NULL;
  if (cls == NULL)
    {
      owned_cls = resolve_boxed_pytype_from_context (G_TYPE_VALUE);
      cls = owned_cls;
    }
  /* Fall back to the base boxed type: pygi_gvalue_wrapper_get only checks
   * the gtype field, not the Python class, so any boxed subtype works. */
  if (cls == NULL)
    cls = (PyObject *)(void *)pygi_gboxed_base_type;
  if (cls == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "GObject.Value Python class not yet registered");
      return NULL;
    }
  GValue *value = g_new0 (GValue, 1);
  if (value == NULL)
    {
      Py_XDECREF (owned_cls);
      PyErr_NoMemory ();
      return NULL;
    }
  g_value_init (value, gtype);
  PyObject *wrapper = pygi_boxed_new_heap (cls, value, G_TYPE_VALUE, sizeof (GValue));
  Py_XDECREF (owned_cls);
  return wrapper;
}

/* Wrap a GValue* as a GObject.Value the caller owns, so it can be handed to
 * introspected functions that take a `const GValue *` (e.g. a namespace's own
 * value_serialize) without the caller touching C. The contents are copied into a
 * fresh GValue, so the source pointer need not outlive the wrapper. Generic: it
 * neither knows nor names the value's GType. */
PyObject *
pygi_gvalue_wrap_pointer (GValue *value)
{
  if (value == NULL)
    Py_RETURN_NONE;
  PyObject *wrapper = pygi_gvalue_new_for_gtype (G_VALUE_TYPE (value));
  if (wrapper == NULL)
    return NULL;
  GValue *dest = NULL;
  if (!pygi_gvalue_wrapper_get (wrapper, &dest) || dest == NULL)
    {
      Py_DECREF (wrapper);
      PyErr_SetString (PyExc_RuntimeError, "could not allocate GValue wrapper");
      return NULL;
    }
  g_value_copy (value, dest);
  return wrapper;
}

static PyObject *
pygi_gerror_to_py (GError *err)
{
  if (err == NULL)
    Py_RETURN_NONE;

  PyObject *factory = pygi_hook_last (pygi_hook_exception_from_gerror);
  if (factory == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "exception_from_gerror hook not registered");
      return NULL;
    }
  return PyObject_CallFunction (factory,
                                "kis",
                                (unsigned long)err->domain,
                                (int)err->code,
                                err->message);
}

static PyObject *
pygi_gvalue_array_to_py (GValueArray *array)
{
  if (array == NULL)
    Py_RETURN_NONE;

  PyObject *list = PyList_New (array->n_values);
  if (list == NULL)
    return NULL;

  for (guint i = 0; i < array->n_values; i++)
    {
      PyObject *item = pygi_gvalue_value_to_py (&array->values[i]);
      if (item == NULL)
        {
          Py_DECREF (list);
          return NULL;
        }
      PyList_SET_ITEM (list, i, item);
    }

  return list;
}

static int
infer_float_value_type (GIArgInfo *arg_info)
{
  if (arg_info == NULL)
    return G_TYPE_DOUBLE;
  const char *name = gi_base_info_get_name ((GIBaseInfo *)arg_info);
  if (name != NULL)
    {
      if (strstr (name, "float") != NULL && strstr (name, "double") == NULL)
        return G_TYPE_FLOAT;
      if (strstr (name, "double") != NULL)
        return G_TYPE_DOUBLE;
    }
  return G_TYPE_DOUBLE;
}

static int
pyobject_get_pygi_gtype (PyObject *obj, GType *out)
{
  if (pygi_gtype_from_gimeta_attr (obj, out) == 0)
    return 0;
  if (!PyErr_ExceptionMatches (PyExc_AttributeError))
    return -1;
  PyErr_Clear ();

  PyObject *py_gtype = PyObject_GetAttrString (obj, "__gtype__");
  if (py_gtype == NULL)
    {
      if (PyErr_ExceptionMatches (PyExc_AttributeError))
        PyErr_Clear ();
      return -1;
    }

  int result = pygi_gtype_from_py_object (py_gtype, out);
  Py_DECREF (py_gtype);
  return result;
}

static int
pyobject_to_gerror (PyObject *obj, GError **out_error)
{
  if (!PyTuple_Check (obj) || PyTuple_GET_SIZE (obj) != 3)
    return 0;

  PyObject *domain_obj = PyTuple_GET_ITEM (obj, 0);
  PyObject *code_obj = PyTuple_GET_ITEM (obj, 1);
  PyObject *message_obj = PyTuple_GET_ITEM (obj, 2);
  if (!PyUnicode_Check (domain_obj) || !PyUnicode_Check (message_obj))
    return 0;

  const char *domain = PyUnicode_AsUTF8 (domain_obj);
  const char *message = PyUnicode_AsUTF8 (message_obj);
  if (domain == NULL || message == NULL)
    return -1;

  long code = PyLong_AsLong (code_obj);
  if (code == -1 && PyErr_Occurred ())
    return -1;

  *out_error = g_error_new_literal (g_quark_from_string (domain), (gint)code, message);
  return *out_error != NULL ? 1 : -1;
}

static GIBaseInfo *
find_registered_type_info_for_gtype (GIRepository *repo, GType gtype)
{
  const char *registered_type_name = g_type_name (gtype);
  g_autoptr (GIBaseInfo) direct = gi_repository_find_by_gtype (repo, gtype);
  if (direct != NULL)
    return g_steal_pointer (&direct);

  if (registered_type_name != NULL && g_str_has_prefix (registered_type_name, "Cairo"))
    {
      g_autoptr (GError) error = NULL;
      if (gi_repository_require (repo, "cairo", NULL, GI_REPOSITORY_LOAD_FLAG_NONE, &error)
          != NULL)
        {
          direct = gi_repository_find_by_gtype (repo, gtype);
          if (direct != NULL)
            return g_steal_pointer (&direct);

          g_autoptr (GIBaseInfo) cairo_info
              = gi_repository_find_by_name (repo, "cairo", registered_type_name + 5);
          if (cairo_info != NULL)
            return g_steal_pointer (&cairo_info);
        }
      else
        g_clear_error (&error);
    }

  size_t n_namespaces = 0;
  g_auto (GStrv) namespaces = gi_repository_get_loaded_namespaces (repo, &n_namespaces);
  for (size_t ni = 0; ni < n_namespaces; ni++)
    {
      const char *namespace_name = namespaces[ni];
      unsigned int n_infos = gi_repository_get_n_infos (repo, namespace_name);
      for (unsigned int ii = 0; ii < n_infos; ii++)
        {
          g_autoptr (GIBaseInfo) info = gi_repository_get_info (repo, namespace_name, ii);
          if (info == NULL || !GI_IS_REGISTERED_TYPE_INFO (info))
            continue;
          GType info_gtype = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)info);
          const char *info_type_name
              = gi_registered_type_info_get_type_name ((GIRegisteredTypeInfo *)info);
          if (info_gtype == gtype
              || (registered_type_name != NULL && info_type_name != NULL
                  && g_strcmp0 (registered_type_name, info_type_name) == 0))
            return g_steal_pointer (&info);
        }
    }

  return NULL;
}

static PyObject *
resolve_boxed_pytype_from_context (GType gtype)
{
  PyObject *context = pygi_namespace_context ();
  if (context == NULL)
    return NULL;

  PyObject *namespace_name_obj = PyObject_GetAttrString (context, "__name__");
  if (namespace_name_obj == NULL)
    {
      PyErr_Clear ();
      return NULL;
    }
  const char *namespace_name = PyUnicode_AsUTF8 (namespace_name_obj);
  if (namespace_name == NULL)
    {
      Py_DECREF (namespace_name_obj);
      PyErr_Clear ();
      return NULL;
    }

  const char *type_name = g_type_name (gtype);
  if (type_name == NULL || !g_str_has_prefix (type_name, namespace_name))
    {
      Py_DECREF (namespace_name_obj);
      return NULL;
    }

  const char *member_name = type_name + strlen (namespace_name);
  if (*member_name == '\0')
    {
      Py_DECREF (namespace_name_obj);
      return NULL;
    }

  PyObject *cls = PyObject_GetAttrString (context, member_name);
  Py_DECREF (namespace_name_obj);
  if (cls == NULL)
    {
      PyErr_Clear ();
      return NULL;
    }
  return cls;
}

int
pygi_py_to_gvalue_inplace (PyObject *h, GValue *value, GIArgInfo *arg_info)
{
  g_return_val_if_fail (value != NULL, -1);
  PyObject *obj = (PyObject *)(h);
  GType gtype = 0;
  GValue *wrapped = NULL;
  if (pygi_gvalue_wrapper_get (obj, &wrapped))
    {
      if (wrapped->g_type == 0)
        {
          PyErr_SetString (PyExc_TypeError, "GObject.Value needs to be initialized first");
          return -1;
        }
      g_value_init (value, G_VALUE_TYPE (wrapped));
      g_value_copy (wrapped, value);
      return 0;
    }
  if (obj == Py_None)
    {
      gtype = G_TYPE_POINTER;
      g_value_init (value, gtype);
      g_value_set_pointer (value, NULL);
    }
  else if (PyUnicode_Check (obj))
    {
      const char *s = PyUnicode_AsUTF8 (obj);
      if (s == NULL)
        return -1;
      g_value_init (value, G_TYPE_STRING);
      g_value_set_string (value, s);
    }
  else if (PyBool_Check (obj))
    {
      g_value_init (value, G_TYPE_BOOLEAN);
      g_value_set_boolean (value, obj == Py_True);
    }
  else if (PyFloat_Check (obj))
    {
      double v = PyFloat_AsDouble (obj);
      if (PyErr_Occurred ())
        return -1;
      gtype = infer_float_value_type (arg_info);
      g_value_init (value, gtype);
      if (gtype == G_TYPE_FLOAT)
        g_value_set_float (value, (gfloat)v);
      else
        g_value_set_double (value, v);
    }
  else if (pyobject_get_pygi_gtype (obj, &gtype) == 0 && g_type_is_a (gtype, G_TYPE_ENUM))
    {
      long v = PyLong_AsLong (obj);
      if (v == -1 && PyErr_Occurred ())
        return -1;
      g_value_init (value, gtype);
      g_value_set_enum (value, (gint)v);
    }
  else if (pyobject_get_pygi_gtype (obj, &gtype) == 0 && g_type_is_a (gtype, G_TYPE_FLAGS))
    {
      unsigned long v = PyLong_AsUnsignedLong (obj);
      if (v == (unsigned long)-1 && PyErr_Occurred ())
        return -1;
      g_value_init (value, gtype);
      g_value_set_flags (value, (guint)v);
    }
  else if (pyobject_get_pygi_gtype (obj, &gtype) == 0)
    {
      return pygi_py_to_gvalue_targeted (gtype, obj, value, "GValue");
    }
  else if (PyLong_Check (obj))
    {
      long v = PyLong_AsLong (obj);
      if (v == -1 && PyErr_Occurred ())
        {
          PyErr_Clear ();
          long long v64 = PyLong_AsLongLong (obj);
          if (v64 == -1 && PyErr_Occurred ())
            {
              PyErr_Clear ();
              unsigned long long uv = PyLong_AsUnsignedLongLong (obj);
              if (uv == (unsigned long long)-1 && PyErr_Occurred ())
                return -1;
              g_value_init (value, G_TYPE_UINT64);
              g_value_set_uint64 (value, (guint64)uv);
            }
          else
            {
              g_value_init (value, G_TYPE_INT64);
              g_value_set_int64 (value, (gint64)v64);
            }
        }
      else if (v > G_MAXINT || v < G_MININT)
        {
          g_value_init (value, G_TYPE_INT64);
          g_value_set_int64 (value, (gint64)v);
        }
      else
        {
          g_value_init (value, G_TYPE_INT);
          g_value_set_int (value, (gint)v);
        }
    }
  else if (PyTuple_Check (obj))
    {
      GError *err = NULL;
      int rc = pyobject_to_gerror (obj, &err);
      if (rc < 0)
        return -1;
      if (rc == 1)
        {
          g_value_init (value, G_TYPE_ERROR);
          g_value_set_boxed (value, err);
        }
      else
        {
          PyErr_Format (PyExc_NotImplementedError,
                        "GValue argument conversion not implemented for Python type %.200s",
                        Py_TYPE (obj)->tp_name);
          return -1;
        }
    }
  else if (PyList_Check (obj))
    {
      Py_ssize_t n = PyList_GET_SIZE (obj);
      gchar **strv = g_new0 (gchar *, (gsize)n + 1);
      for (Py_ssize_t i = 0; i < n; i++)
        {
          PyObject *item = PyList_GET_ITEM (obj, i);
          if (!PyUnicode_Check (item))
            {
              g_strfreev (strv);
              PyErr_Format (PyExc_NotImplementedError,
                            "GValue list conversion only supports str items, not %.200s",
                            Py_TYPE (item)->tp_name);
              return -1;
            }
          const char *s = PyUnicode_AsUTF8 (item);
          if (s == NULL)
            {
              g_strfreev (strv);
              return -1;
            }
          strv[i] = g_strdup (s);
        }
      g_value_init (value, G_TYPE_STRV);
      g_value_take_boxed (value, strv);
    }
  else
    {
      PyObject *py = (PyObject *)(void *)(h);
      if (pygi_gobject_type != NULL && PyObject_TypeCheck (py, pygi_gobject_type))
        {
          GObject *go = pygi_gobject_get (py);
          if (go == NULL)
            {
              if (PyErr_Occurred ())
                PyErr_Clear ();
              PyErr_SetString (PyExc_TypeError, "expected a pygi GObject wrapper");
              return -1;
            }
          g_value_init (value, G_OBJECT_TYPE (go));
          g_value_set_object (value, go);
        }
      else
        {
          PyErr_Format (PyExc_NotImplementedError,
                        "GValue argument conversion not implemented for Python type %.200s",
                        Py_TYPE (obj)->tp_name);
          return -1;
        }
    }
  return 0;
}

/* Target-typed Python -> GValue conversion. The caller already knows
 * the destination GType (typically from a GParamSpec on a property
 * set, but anywhere a target GType is available works). Distinct from
 * pygi_py_to_gvalue_inplace, which infers the GType from the Python
 * object - that path can't disambiguate cases like `[a, b]` (could be
 * GStrv or a generic list), so target-typed callers MUST come through
 * here. `context` is folded into error messages (e.g. property name);
 * NULL is fine. */
int
pygi_py_to_gvalue_targeted (GType type, PyObject *obj, GValue *value, const char *context)
{
  PyGIType pygi_type = { 0 };
  if (pygi_type_from_gtype (type, &pygi_type) == 0)
    {
      switch (pygi_type.kind)
        {
        case PYGI_TYPE_BOOLEAN:
        case PYGI_TYPE_INT8:
        case PYGI_TYPE_UINT8:
        case PYGI_TYPE_INT32:
        case PYGI_TYPE_UINT32:
        case PYGI_TYPE_INT64:
        case PYGI_TYPE_UINT64:
        case PYGI_TYPE_FLOAT:
        case PYGI_TYPE_DOUBLE:
        case PYGI_TYPE_UTF8:
        case PYGI_TYPE_GTYPE:
        case PYGI_TYPE_POINTER:
          {
            PyGIValue pygi_value = pygi_value_for_gvalue (&pygi_type, value);
            return pygi_value_from_py (obj, &pygi_value);
          }
        default:
          break;
        }
    }

  g_value_init (value, type);

  if (type == G_TYPE_VALUE)
    {
      GValue *inner = g_new0 (GValue, 1);
      if (pygi_py_to_gvalue_inplace (obj, inner, NULL) != 0)
        {
          g_free (inner);
          return -1;
        }
      g_value_take_boxed (value, inner);
      return 0;
    }

  if (g_type_is_a (type, G_TYPE_PARAM))
    {
      GParamSpec *pspec = NULL;
      if (pygi_param_spec_from_py (obj, &pspec) != 0)
        return -1;
      g_value_set_param (value, pspec);
      return 0;
    }

  /* Dispatch on the fundamental, not the exact type. Enum/flags
   * subtypes route to G_TYPE_ENUM / G_TYPE_FLAGS via this; specific
   * boxed shapes (G_TYPE_STRV, G_TYPE_VARIANT) need an inner
   * `type == G_TYPE_X` check. */
  switch (G_TYPE_FUNDAMENTAL (type))
    {
    case G_TYPE_STRING:
    case G_TYPE_BOOLEAN:
    case G_TYPE_CHAR:
    case G_TYPE_UCHAR:
    case G_TYPE_INT:
    case G_TYPE_UINT:
    case G_TYPE_LONG:
    case G_TYPE_ULONG:
    case G_TYPE_INT64:
    case G_TYPE_UINT64:
    case G_TYPE_FLOAT:
    case G_TYPE_DOUBLE:
      g_assert_not_reached ();

    case G_TYPE_ENUM:
      {
        /* PyGObject-compatible: a string maps to the enum value via
         * nick (preferred) or short-name lookup. gnome-music does
         * `Adw.ViewSwitcher(halign="center")` - the str routes here
         * for the GTK_ALIGN_CENTER enum slot. */
        if (PyUnicode_Check (obj))
          {
            const char *s = PyUnicode_AsUTF8 (obj);
            if (s == NULL)
              return -1;
            GEnumClass *eclass = (GEnumClass *)g_type_class_ref (type);
            GEnumValue *ev = g_enum_get_value_by_nick (eclass, s);
            if (ev == NULL)
              ev = g_enum_get_value_by_name (eclass, s);
            if (ev == NULL)
              {
                PyErr_Format (PyExc_ValueError,
                              "%s: %s is not a valid value for %s",
                              context ? context : "enum",
                              s,
                              g_type_name (type));
                g_type_class_unref (eclass);
                return -1;
              }
            g_value_set_enum (value, ev->value);
            g_type_class_unref (eclass);
            return 0;
          }
        long v = PyLong_AsLong (obj);
        if (v == -1 && PyErr_Occurred ())
          return -1;
        g_value_set_enum (value, (gint)v);
      }
      return 0;

    case G_TYPE_FLAGS:
      {
        /* String -> flags lookup (one nick at a time; "|"-joined for
         * compound). Matches pygobject. */
        if (PyUnicode_Check (obj))
          {
            const char *s = PyUnicode_AsUTF8 (obj);
            if (s == NULL)
              return -1;
            GFlagsClass *fclass = (GFlagsClass *)g_type_class_ref (type);
            guint accum = 0;
            const char *p = s;
            while (*p)
              {
                const char *bar = strchr (p, '|');
                gsize tok_len = bar ? (gsize)(bar - p) : strlen (p);
                /* Trim ASCII whitespace. */
                while (tok_len > 0 && (p[0] == ' ' || p[0] == '\t'))
                  {
                    p++;
                    tok_len--;
                  }
                while (tok_len > 0 && (p[tok_len - 1] == ' ' || p[tok_len - 1] == '\t'))
                  tok_len--;
                if (tok_len > 0)
                  {
                    g_autofree char *tok = g_strndup (p, tok_len);
                    GFlagsValue *fv = g_flags_get_value_by_nick (fclass, tok);
                    if (fv == NULL)
                      fv = g_flags_get_value_by_name (fclass, tok);
                    if (fv == NULL)
                      {
                        PyErr_Format (PyExc_ValueError,
                                      "%s: %s is not a valid flag for %s",
                                      context ? context : "flags",
                                      tok,
                                      g_type_name (type));
                        g_type_class_unref (fclass);
                        return -1;
                      }
                    accum |= fv->value;
                  }
                if (!bar)
                  break;
                p = bar + 1;
              }
            g_value_set_flags (value, accum);
            g_type_class_unref (fclass);
            return 0;
          }
        unsigned long v = PyLong_AsUnsignedLong (obj);
        if (v == (unsigned long)-1 && PyErr_Occurred ())
          return -1;
        g_value_set_flags (value, (guint)v);
      }
      return 0;

    case G_TYPE_OBJECT:
      if (obj == Py_None)
        {
          g_value_set_object (value, NULL);
          return 0;
        }
      {
        GObject *go = pygi_gobject_get (obj);
        if (go == NULL)
          {
            PyErr_SetString (PyExc_TypeError, "expected a pygi GObject wrapper");
            return -1;
          }
        g_value_set_object (value, go);
      }
      return 0;

    /* GInterface-typed destination (e.g. Gtk.Picture.paintable holds a
     * GdkPaintable): GValue type is the interface itself, not a GObject
     * subtype, so g_value_set_object would trip its G_VALUE_HOLDS_OBJECT
     * assert. g_value_set_instance dispatches through the value table
     * and accepts any GObject that g_type_is_a()'s the interface. */
    case G_TYPE_INTERFACE:
      if (obj == Py_None)
        {
          g_value_set_instance (value, NULL);
          return 0;
        }
      {
        GObject *go = pygi_gobject_get (obj);
        if (go == NULL)
          {
            PyErr_SetString (PyExc_TypeError, "expected a pygi GObject wrapper");
            return -1;
          }
        if (!g_type_is_a (G_OBJECT_TYPE (go), type))
          {
            PyErr_Format (PyExc_TypeError,
                          "%s: %s does not implement %s",
                          context ? context : "<unknown>",
                          G_OBJECT_TYPE_NAME (go),
                          g_type_name (type));
            return -1;
          }
        g_value_set_instance (value, go);
      }
      return 0;

    case G_TYPE_VARIANT:
      /* GVariant property: accept either a GLib.Variant wrapper or
       * None. pygi_py_item_to_gvariant returns a freshly-sunk
       * GVariant* and we hand it to the value via take_variant so the
       * caller (us) doesn't end up with a dangling extra ref. */
      {
        if (obj != Py_None
            && !(PyObject_TypeCheck (obj, pygi_gboxed_base_type)
                 && ((PyGIGLibBoxed *)obj)->gtype == G_TYPE_VARIANT))
          {
            PyErr_SetString (PyExc_TypeError,
                             "GVariant property value must be GLib.Variant or None");
            return -1;
          }
        void *gv = NULL;
        if (pygi_py_item_to_gvariant (obj, &gv) != 0)
          return -1;
        g_value_take_variant (value, (GVariant *)gv);
      }
      return 0;

    case G_TYPE_BOXED:
      if (type == G_TYPE_ERROR)
        {
          GError *err = NULL;
          int rc = pygi_error_from_py (obj, &err);
          if (rc <= 0)
            {
              if (rc == 0)
                PyErr_Format (PyExc_TypeError,
                              "expected GLib.Error, not %.200s",
                              Py_TYPE (obj)->tp_name);
              return -1;
            }
          if (err == NULL)
            {
              g_value_set_boxed (value, NULL);
              return 0;
            }
          g_value_take_boxed (value, err);
          return 0;
        }
      /* None -> NULL boxed slot. Applies to any boxed type, including
       * GPtrArray/GArray/GHashTable in signal emit args where the app
       * has no convenient way to build a C container instance from
       * Python. Without this every emit of a container-typed signal
       * arg would TypeError. */
      if (obj == Py_None)
        {
          g_value_set_boxed (value, NULL);
          return 0;
        }
      /* Registered coercion: try to convert a Python object to the expected
       * boxed type (e.g. re.Pattern → GLib.Regex).  Real GLib wrappers
       * flow through the generic boxed path below and never reach this. */
      {
        PyObject *coerced = pygi_call_coercion (type, obj);
        if (coerced != NULL)
          {
            gpointer boxed_ptr = NULL;
            pygi_boxed_get (coerced, &boxed_ptr);
            if (boxed_ptr != NULL)
              {
                g_value_set_boxed (value, boxed_ptr);
                Py_DECREF (coerced);
                return 0;
              }
            Py_DECREF (coerced);
            if (!PyErr_Occurred ())
              PyErr_SetString (PyExc_TypeError,
                               "coercion did not return a boxed wrapper");
            return -1;
          }
        if (PyErr_Occurred ())
          return -1;
        /* No coercion registered — fall through to the generic boxed path. */
      }
      /* GLib.DateTime/Date/TimeZone: accept the matching stdlib datetime
       * object. Real GLib wrappers flow through the generic boxed path below. */
      if (type == G_TYPE_DATE_TIME && pygi_py_datetime_check (obj))
        {
          GDateTime *dt = pygi_gdatetime_from_py (obj);
          if (dt == NULL)
            return -1;
          g_value_take_boxed (value, dt);
          return 0;
        }
      if (type == G_TYPE_DATE && pygi_py_date_check (obj))
        {
          GDate *d = pygi_gdate_from_py (obj);
          if (d == NULL)
            return -1;
          g_value_take_boxed (value, d);
          return 0;
        }
      if (type == G_TYPE_TIME_ZONE && pygi_py_tzinfo_check (obj))
        {
          GTimeZone *tz = pygi_gtimezone_from_py (obj);
          if (tz == NULL)
            return -1;
          g_value_take_boxed (value, tz);
          return 0;
        }
      /* GByteArray: accept Python bytes (the obvious shape) so apps
       * that need a `(some-byte-array)` property - file-data passing
       * patterns are the typical case - can hand over a `b"..."`. */
      if (type == G_TYPE_BYTE_ARRAY)
        {
          if (obj == Py_None)
            {
              g_value_set_boxed (value, NULL);
              return 0;
            }
          Py_buffer view;
          if (PyObject_GetBuffer (obj, &view, PyBUF_SIMPLE) != 0)
            return -1;
          GByteArray *ga = g_byte_array_sized_new ((guint)view.len);
          g_byte_array_append (ga, (const guint8 *)view.buf, (guint)view.len);
          PyBuffer_Release (&view);
          g_value_take_boxed (value, ga);
          return 0;
        }
      /* G_TYPE_STRV (gchar**): accept any Python sequence of str / None.
       * Used by Gtk.AboutDialog.authors / .documenters / .artists.
       * Other boxed subtypes fall through to the unsupported error
       * below - they need per-type marshalling (g_boxed_copy etc.). */
      if (type == G_TYPE_STRV)
        {
          if (obj == Py_None)
            {
              g_value_set_boxed (value, NULL);
              return 0;
            }
          if (PyUnicode_Check (obj))
            {
              PyErr_SetString (PyExc_TypeError, "GStrv value must be a sequence of str, not str");
              return -1;
            }
          PyObject *seq = PySequence_Fast (obj, "expected a sequence of str for GStrv");
          if (seq == NULL)
            return -1;
          Py_ssize_t n = PySequence_Fast_GET_SIZE (seq);
          gchar **strv = g_new0 (gchar *, (gsize)n + 1);
          for (Py_ssize_t i = 0; i < n; i++)
            {
              PyObject *item = PySequence_Fast_GET_ITEM (seq, i); /* borrowed */
              if (!PyUnicode_Check (item))
                {
                  g_strfreev (strv);
                  Py_DECREF (seq);
                  PyErr_Format (PyExc_TypeError,
                                "GStrv %s: item %zd is not a str",
                                context ? context : "<unknown>",
                                (Py_ssize_t)i);
                  return -1;
                }
              const char *s = PyUnicode_AsUTF8 (item);
              if (s == NULL)
                {
                  g_strfreev (strv);
                  Py_DECREF (seq);
                  return -1;
                }
              strv[i] = g_strdup (s);
            }
          Py_DECREF (seq);
          g_value_take_boxed (value, strv);
          return 0;
        }
      /* General path: pygir boxed wrapper for any GType (GDateTime,
       * GBytes, Gdk.RGBA, ...). Real apps lean on it via
       * `GObject.Property(type=GLib.DateTime, default=None)` shapes
       * (gnome-music's CoreSong.last_played). The wrapper carries the
       * boxed pointer + GType in `PyGIGLibBoxed`. We only accept
       * wrappers whose GType is compatible with the pspec's declared
       * boxed type - otherwise g_value_set_boxed would corrupt the
       * GValue. */
      if (PyObject_TypeCheck (obj, pygi_gboxed_base_type))
        {
          PyGIGLibBoxed *wrap = (PyGIGLibBoxed *)obj;
          if (wrap->gtype != 0 && g_type_is_a (wrap->gtype, type))
            {
              g_value_set_boxed (value, wrap->boxed);
              return 0;
            }
        }
      {
        GIRepository *repo = pygi_shared_repository ();
        g_autoptr (GIBaseInfo) info = NULL;
        if (repo != NULL)
          info = find_registered_type_info_for_gtype (repo, type);
        if (info != NULL)
          {
            int cairo_rc = pygi_foreign_cairo_boxed_from_py (obj, info, value);
            if (cairo_rc <= 0)
              return cairo_rc;
          }
      }
      break;

    case G_TYPE_POINTER:
      /* `type=object` properties register as g_param_spec_pointer.
       * Store the Python wrapper (never the underlying GObject), so
       * `pygi_gvalue_value_to_py`'s G_TYPE_POINTER path can Py_NewRef
       * it back into a Python object. Storing the raw GObject would
       * segfault on readback (the value_to_py treats the slot as a
       * PyObject* and increments its refcount). Lifetime of the
       * stored PyObject* is tied to wherever the caller's setter
       * stashed it on the instance - the GValue itself doesn't
       * INCREF (matches pygir's existing G_TYPE_POINTER read path
       * which Py_NewRef's, not Py_BorrowedRef's). */
      g_assert_not_reached ();

    default:
      break;
    }

  /* Instantiatable fundamentals that aren't GObject/GBoxed (GtkExpression
   * is the prominent case: its fundamental is itself, registered with
   * G_TYPE_FLAG_INSTANTIATABLE). The unwrap path returns the raw fundamental
   * pointer just like a GObject; g_value_set_instance routes through the
   * type's value table (which calls the type-specific ref). */
  if (G_TYPE_IS_INSTANTIATABLE (type))
    {
      if (obj == Py_None)
        {
          g_value_set_instance (value, NULL);
          return 0;
        }
      GObject *inst = pygi_gobject_get (obj);
      if (inst == NULL)
        return -1;
      if (!g_type_is_a (G_TYPE_FROM_INSTANCE (inst), type))
        {
          PyErr_Format (PyExc_TypeError,
                        "%s: %s is not a %s",
                        context ? context : "<unknown>",
                        g_type_name (G_TYPE_FROM_INSTANCE (inst)),
                        g_type_name (type));
          return -1;
        }
      g_value_set_instance (value, inst);
      return 0;
    }

  int hook_result = gvalue_call_from_py_hook (obj, type, value);
  if (hook_result <= 0)
    return hook_result;

  PyErr_Format (PyExc_NotImplementedError,
                "%s has unsupported GType %s",
                context ? context : "GValue",
                g_type_name (type));
  return -1;
}

int
pygi_gvalue_from_py (PyObject *h, GIArgInfo *arg_info, GIArgument *out, PyGIArgCleanup *cleanup)
{
  g_return_val_if_fail (out != NULL, -1);
  g_return_val_if_fail (cleanup != NULL, -1);
  GValue *wrapped = NULL;
  if (pygi_gvalue_wrapper_get (h, &wrapped))
    {
      if (wrapped->g_type == 0)
        {
          PyErr_SetString (PyExc_TypeError, "GObject.Value needs to be initialized first");
          return -1;
        }
      out->v_pointer = wrapped;
      cleanup->kind = PYGI_ARG_CLEANUP_NONE;
      cleanup->ptr = NULL;
      return 0;
    }
  GValue *value = g_new0 (GValue, 1);
  if (value == NULL)
    {
      PyErr_NoMemory ();
      return -1;
    }
  if (pygi_py_to_gvalue_inplace (h, value, arg_info) != 0)
    {
      g_free (value);
      return -1;
    }
  out->v_pointer = value;
  cleanup->kind = PYGI_ARG_CLEANUP_GVALUE;
  cleanup->ptr = value;
  return 0;
}

PyObject *
pygi_gvalue_value_to_py (GValue *value)
{
  if (value == NULL)
    return Py_XNewRef (Py_None);
  GType gtype = G_VALUE_TYPE (value);
  if (!gtype)
    return Py_XNewRef (Py_None);

  PyGIType pygi_type = { 0 };
  if (pygi_type_from_gvalue (value, &pygi_type) == 0)
    {
      switch (pygi_type.kind)
        {
        case PYGI_TYPE_BOOLEAN:
        case PYGI_TYPE_INT8:
        case PYGI_TYPE_UINT8:
        case PYGI_TYPE_INT32:
        case PYGI_TYPE_UINT32:
        case PYGI_TYPE_INT64:
        case PYGI_TYPE_UINT64:
        case PYGI_TYPE_FLOAT:
        case PYGI_TYPE_DOUBLE:
        case PYGI_TYPE_UTF8:
        case PYGI_TYPE_GTYPE:
        case PYGI_TYPE_POINTER:
          {
            PyGIValue pygi_value = pygi_value_for_gvalue (&pygi_type, value);
            return pygi_value_to_py (&pygi_value);
          }
        default:
          break;
        }
    }

  if (gtype == G_TYPE_ERROR)
    {
      GError *err = g_value_get_boxed (value);
      return pygi_gerror_to_py (err);
    }
  if (g_strcmp0 (g_type_name (gtype), "GValueArray") == 0)
    return pygi_gvalue_array_to_py ((GValueArray *)g_value_get_boxed (value));
  if (gtype == G_TYPE_VARIANT)
    {
      GVariant *v = g_value_get_variant (value);
      PyObject *w = pygi_wrap_variant (NULL, v, GI_TRANSFER_NOTHING);
      return w != NULL ? (PyObject *)(w) : NULL;
    }
  if (gtype == G_TYPE_VALUE)
    {
      GValue *inner = g_value_get_boxed (value);
      return pygi_gvalue_value_to_py (inner);
    }
  if (G_TYPE_IS_OBJECT (gtype))
    {
      GObject *obj = g_value_get_object (value);
      if (obj == NULL)
        return Py_XNewRef (Py_None);
      return pygi_gobject_to_py (obj, GI_TRANSFER_NOTHING);
    }
  /* Interface-typed GValue (e.g. a GdkPaintable held by
   * Gtk.Picture.paintable): the value table stores a v_pointer to a
   * GObject implementing the interface. g_value_get_object would fail
   * the G_VALUE_HOLDS_OBJECT assert, so reach for it via the value
   * table's peek hook. */
  if (G_TYPE_IS_INTERFACE (gtype))
    {
      gpointer ptr = g_value_peek_pointer (value);
      if (ptr == NULL || !G_IS_OBJECT (ptr))
        return Py_XNewRef (Py_None);
      return pygi_gobject_to_py ((GObject *)ptr, GI_TRANSFER_NOTHING);
    }
  if (g_type_is_a (gtype, G_TYPE_PARAM))
    {
      GParamSpec *pspec = g_value_get_param (value);
      PyObject *wrapper = pygi_param_spec_new (pspec);
      return wrapper != NULL ? (PyObject *)(wrapper) : NULL;
    }
  if (g_type_is_a (gtype, G_TYPE_ENUM))
    return PyLong_FromLong (g_value_get_enum (value));
  if (g_type_is_a (gtype, G_TYPE_FLAGS))
    return PyLong_FromUnsignedLong (g_value_get_flags (value));

  /* G_TYPE_STRV: gchar** boxed array. */
  if (gtype == G_TYPE_STRV)
    {
      gchar **strv = (gchar **)g_value_get_boxed (value);
      return pygi_strv_to_py_list (strv, GI_TRANSFER_NOTHING);
    }

  if (gtype == G_TYPE_BYTE_ARRAY)
    {
      GByteArray *array = (GByteArray *)g_value_get_boxed (value);
      if (array == NULL)
        return PyBytes_FromStringAndSize ("", 0);
      return PyBytes_FromStringAndSize ((const char *)array->data, (Py_ssize_t)array->len);
    }

  /* G_TYPE_HASH_TABLE: opaque return as repr (just non-None). */
  if (g_type_is_a (gtype, G_TYPE_HASH_TABLE))
    {
      if (g_value_get_boxed (value) == NULL)
        return Py_XNewRef (Py_None);
      return PyUnicode_FromString ("<GHashTable>");
    }

  /* For other boxed types (G_TYPE_DATE, etc.) return non-None repr. */
  if (g_type_is_a (gtype, G_TYPE_BOXED))
    {
      gpointer boxed = g_value_get_boxed (value);
      if (boxed == NULL)
        return Py_XNewRef (Py_None);
      PyObject *cls = pygi_class_registry_get_pytype_for_gtype (gtype);
      PyObject *owned_cls = NULL;
      g_autoptr (GIBaseInfo) info = NULL;
      if (cls == NULL)
        {
          GIRepository *repo = pygi_shared_repository ();
          owned_cls = resolve_boxed_pytype_from_context (gtype);
          cls = owned_cls;
          if (repo != NULL && cls == NULL)
            {
              info = find_registered_type_info_for_gtype (repo, gtype);
              if (info == NULL && gtype == G_TYPE_ARRAY)
                {
                  g_autoptr (GError) error = NULL;
                  if (gi_repository_require (repo,
                                             "GLib",
                                             "2.0",
                                             GI_REPOSITORY_LOAD_FLAG_NONE,
                                             &error)
                      != NULL)
                    info = gi_repository_find_by_name (repo, "GLib", "Array");
                  else
                    g_clear_error (&error);
                }
              /* Foreign cairo Surface/Context boxed in a GValue (e.g. as
               * a signal handler argument): hand pycairo a wrapper. */
              if (info != NULL)
                {
                  PyObject *cw = pygi_foreign_cairo_to_py (info, boxed, GI_TRANSFER_NOTHING);
                  if (cw != NULL)
                    return (PyObject *)(cw);
                  if ((PyErr_Occurred () != NULL))
                    return NULL;
                }
              if (info != NULL && (GI_IS_STRUCT_INFO (info) || GI_IS_UNION_INFO (info)))
                {
                  PyObject *h_cls
                      = pygi_build_struct_class (gi_base_info_get_namespace (info), info);
                  if (!(h_cls == NULL))
                    {
                      cls = (PyObject *)(void *)(h_cls);
                      Py_DECREF (cls);
                    }
                  else if ((PyErr_Occurred () != NULL))
                    return NULL;
                }
            }
        }
      if (cls != NULL)
        {
          int transfer_full = 0;
          if (gtype == G_TYPE_ARRAY && boxed != NULL)
            {
              boxed = g_array_ref ((GArray *)boxed);
              transfer_full = 1;
            }
          else
            {
              boxed = g_boxed_copy (gtype, boxed);
              if (boxed == NULL)
                return Py_XNewRef (Py_None);
              transfer_full = 1;
            }
          PyObject *wrapper = pygi_boxed_new (cls, boxed, gtype, transfer_full);
          Py_XDECREF (owned_cls);
          return wrapper != NULL ? (PyObject *)(wrapper) : NULL;
        }
      Py_XDECREF (owned_cls);
      const char *type_name = g_type_name (gtype);
      return PyUnicode_FromString (type_name ? type_name : "<boxed>");
    }

  PyObject *hook_result = gvalue_call_to_py_hook (gtype, value);
  if (hook_result != NULL)
    return hook_result;
  if (!PyErr_ExceptionMatches (PyExc_AttributeError))
    return NULL;
  PyErr_Clear ();

  PyErr_Format (PyExc_NotImplementedError,
                "GValue return conversion: unsupported GType %s (%" G_GSIZE_FORMAT ")",
                g_type_name (gtype) != NULL ? g_type_name (gtype) : "<unknown>",
                (gsize)gtype);
  return NULL;
}

PyObject *
pygi_gvalue_to_py (GIArgument *arg)
{
  g_return_val_if_fail (arg != NULL, NULL);
  return pygi_gvalue_value_to_py ((GValue *)arg->v_pointer);
}
