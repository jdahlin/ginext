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

#include "common.h"
#include "GObject/Object-info.h"
#include "GIRepository/BaseInfo.h"
#include "GIRepository/Info.h"

#include <dlfcn.h>
#include <girepository/girepository.h>
#include <stdlib.h>
#include <string.h>

static GIRepository *shared_repository = NULL;
static gsize shared_repository_once = 0;
static unsigned long long invoke_plan_gi_metadata_calls = 0;
static unsigned long long invoke_hot_gi_metadata_calls = 0;

static void
record_plan_gi_metadata_call (void)
{
  invoke_plan_gi_metadata_calls++;
}

void
pygi_ginext_record_plan_gi_metadata_call (void)
{
  record_plan_gi_metadata_call ();
}

static void
init_shared_repository (void)
{
  shared_repository = gi_repository_new ();
}

GIRepository *
ginext_shared_repository (void)
{
  if (g_once_init_enter (&shared_repository_once))
    {
      init_shared_repository ();
      g_once_init_leave (&shared_repository_once, 1);
    }
  return shared_repository;
}

static void
prepend_env_typelib_paths (GIRepository *repo)
{
  const char *path = g_getenv ("GI_TYPELIB_PATH");
  if (path == NULL || path[0] == '\0')
    return;
  g_auto (GStrv) parts = g_strsplit (path, G_SEARCHPATH_SEPARATOR_S, -1);
  for (gsize i = 0; parts != NULL && parts[i] != NULL; i++)
    {
      if (parts[i][0] != '\0')
        gi_repository_prepend_search_path (repo, parts[i]);
    }
}

/* Wrap a transfer-full GIBaseInfo* as its native GIRepository.*Info type,
 * consuming the caller's ref. gi_info_to_py takes its own ref, so we release
 * the one the gi_*_get_* getter handed us. NULL maps to None. */
static PyObject *
info_to_py_owned (GIBaseInfo *info)
{
  PyObject *obj = gi_info_to_py (info);
  if (info != NULL)
    gi_base_info_unref (info);
  return obj;
}

#define info_from_capsule gi_info_from_py

static int
parse_typelib_filename (const char *fname, char **name_out, char **version_out)
{
  size_t n = strlen (fname);
  const char *suffix = ".typelib";
  size_t slen = strlen (suffix);
  if (n <= slen || strcmp (fname + n - slen, suffix) != 0)
    return 0;

  size_t stem_len = n - slen;
  const char *dash = NULL;
  for (size_t i = stem_len; i > 0; i--)
    {
      if (fname[i - 1] == '-')
        {
          dash = fname + i - 1;
          break;
        }
    }
  if (dash == NULL || dash == fname || dash == fname + stem_len - 1)
    return 0;

  *name_out = g_strndup (fname, (size_t)(dash - fname));
  *version_out = g_strndup (dash + 1, stem_len - (size_t)(dash - fname) - 1);
  return 1;
}

static int
version_compare_desc (const char *a, const char *b)
{
  for (int i = 0; i < 2; i++)
    {
      char *aend = NULL;
      char *bend = NULL;
      long av = strtol (a, &aend, 10);
      long bv = strtol (b, &bend, 10);
      int aok = (aend != a);
      int bok = (bend != b);
      if (!aok && !bok)
        return strcmp (b, a);
      if (!aok)
        return 1;
      if (!bok)
        return -1;
      if (av != bv)
        return (bv > av) ? 1 : -1;
      a = (*aend == '.') ? aend + 1 : "0";
      b = (*bend == '.') ? bend + 1 : "0";
    }
  return 0;
}

static int
version_compare_gptr (gconstpointer a, gconstpointer b)
{
  return version_compare_desc (*(const char *const *)a, *(const char *const *)b);
}

PyObject *
py_installed_versions (PyObject *module G_GNUC_UNUSED, PyObject *Py_UNUSED (args))
{
  GIRepository *repo = ginext_shared_repository ();
  if (repo == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "gi_repository_new failed");
      return NULL;
    }

  size_t n_paths = 0;
  const char *const *paths = gi_repository_get_search_path (repo, &n_paths);
  g_autoptr (GHashTable) by_ns
      = g_hash_table_new_full (g_str_hash, g_str_equal, g_free, (GDestroyNotify)g_ptr_array_unref);

  for (size_t i = 0; i < n_paths; i++)
    {
      const char *dir_path = paths[i];
      if (dir_path == NULL)
        continue;
      g_autoptr (GDir) dir = g_dir_open (dir_path, 0, NULL);
      if (dir == NULL)
        continue;

      const char *entry = NULL;
      while ((entry = g_dir_read_name (dir)) != NULL)
        {
          char *ns = NULL;
          char *ver = NULL;
          if (!parse_typelib_filename (entry, &ns, &ver))
            continue;

          GPtrArray *versions = g_hash_table_lookup (by_ns, ns);
          if (versions == NULL)
            {
              versions = g_ptr_array_new_with_free_func (g_free);
              g_hash_table_insert (by_ns, ns, versions);
            }
          else
            {
              g_free (ns);
            }

          gboolean dup = FALSE;
          for (guint k = 0; k < versions->len; k++)
            {
              if (strcmp (g_ptr_array_index (versions, k), ver) == 0)
                {
                  dup = TRUE;
                  break;
                }
            }
          if (dup)
            g_free (ver);
          else
            g_ptr_array_add (versions, ver);
        }
    }

  PyObject *result = PyDict_New ();
  if (result == NULL)
    return NULL;

  GHashTableIter iter;
  g_hash_table_iter_init (&iter, by_ns);
  gpointer k = NULL;
  gpointer v = NULL;
  while (g_hash_table_iter_next (&iter, &k, &v))
    {
      const char *ns = k;
      GPtrArray *versions = v;
      g_ptr_array_sort (versions, version_compare_gptr);

      PyObject *list = PyList_New ((Py_ssize_t)versions->len);
      if (list == NULL)
        {
          Py_DECREF (result);
          return NULL;
        }
      for (guint i = 0; i < versions->len; i++)
        {
          PyObject *s = PyUnicode_FromString (g_ptr_array_index (versions, i));
          if (s == NULL)
            {
              Py_DECREF (list);
              Py_DECREF (result);
              return NULL;
            }
          PyList_SET_ITEM (list, (Py_ssize_t)i, s);
        }
      if (PyDict_SetItemString (result, ns, list) < 0)
        {
          Py_DECREF (list);
          Py_DECREF (result);
          return NULL;
        }
      Py_DECREF (list);
    }

  return result;
}

PyObject *
py_require_namespace (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  const char *name = NULL;
  const char *version = NULL;
  if (!PyArg_ParseTuple (args, "ss", &name, &version))
    return NULL;

  GIRepository *repo = ginext_shared_repository ();
  if (repo == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "gi_repository_new failed");
      return NULL;
    }
  prepend_env_typelib_paths (repo);

  g_autoptr (GError) error = NULL;
  if (gi_repository_require (repo, name, version, GI_REPOSITORY_LOAD_FLAG_NONE, &error) == NULL)
    {
      PyErr_Format (PyExc_ImportError,
                    "gi_repository_require(%s, %s) failed: %s",
                    name,
                    version,
                    error && error->message ? error->message : "unknown error");
      return NULL;
    }

  size_t n_libs = 0;
  g_autoptr (GIRepository) lookup_repo = gi_repository_new ();
  const char *const *libs = NULL;
  if (lookup_repo != NULL)
    {
      g_autoptr (GError) lookup_error = NULL;
      if (gi_repository_require (lookup_repo,
                                 name,
                                 version,
                                 GI_REPOSITORY_LOAD_FLAG_NONE,
                                 &lookup_error)
          != NULL)
        libs = gi_repository_get_shared_libraries (lookup_repo, name, &n_libs);
    }
  if (libs != NULL)
    {
      for (size_t i = 0; i < n_libs; i++)
        {
          const char *p = libs[i];
          while (*p)
            {
              const char *q = strchr (p, ',');
              size_t len = q ? (size_t)(q - p) : strlen (p);
              char soname[256];
              if (len < sizeof soname)
                {
                  memcpy (soname, p, len);
                  soname[len] = '\0';
                  dlopen (soname, RTLD_LAZY | RTLD_GLOBAL);
                }
              p += len;
              if (q)
                p++;
            }
        }
    }

  const char *loaded = gi_repository_get_version (repo, name);
  return PyUnicode_FromString (loaded ? loaded : version);
}

static const char *
kind_for_info (GIBaseInfo *info)
{
  if (GI_IS_FUNCTION_INFO (info))
    return "function";
  if (GI_IS_OBJECT_INFO (info))
    return "object";
  if (GI_IS_STRUCT_INFO (info))
    return "record";
  if (GI_IS_UNION_INFO (info))
    return "union";
  if (GI_IS_FLAGS_INFO (info))
    return "flags";
  if (GI_IS_ENUM_INFO (info))
    return "enum";
  if (GI_IS_INTERFACE_INFO (info))
    return "interface";
  if (GI_IS_CONSTANT_INFO (info))
    return "constant";
  return "unsupported";
}

PyObject *
py_namespace_find (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  const char *namespace_name = NULL;
  const char *version = NULL;
  const char *attr = NULL;
  if (!PyArg_ParseTuple (args, "sss", &namespace_name, &version, &attr))
    return NULL;

  GIRepository *repo = ginext_shared_repository ();
  if (repo == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "gi_repository_new failed");
      return NULL;
    }

  g_autoptr (GError) error = NULL;
  if (gi_repository_require (repo, namespace_name, version, GI_REPOSITORY_LOAD_FLAG_NONE, &error)
      == NULL)
    {
      PyErr_Format (PyExc_ImportError,
                    "gi_repository_require(%s, %s) failed: %s",
                    namespace_name,
                    version,
                    error && error->message ? error->message : "unknown error");
      return NULL;
    }

  GIBaseInfo *info = gi_repository_find_by_name (repo, namespace_name, attr);
  if (info == NULL)
    {
      PyErr_Format (PyExc_AttributeError, "%s has no attribute %s", namespace_name, attr);
      return NULL;
    }

  const char *kind = kind_for_info (info);

  /* Return a native GIRepository.*Info object. gi_info_to_py takes its own ref,
   * so release ours unconditionally. */
  PyObject *wrapper = gi_info_to_py (info);
  gi_base_info_unref (info);
  if (wrapper == NULL)
    return NULL;
  return Py_BuildValue ("sN", kind, wrapper);
}

/* StructInfo.record_info() / UnionInfo.record_info() — metadata dict for the
 * record builder. METH_NOARGS method on both types. */
PyObject *
ginext_record_info_method (PyObject *self, PyObject *Py_UNUSED (args))
{
  GIBaseInfo *base = PYGI_INFO (self);
  if (!GI_IS_STRUCT_INFO (base) && !GI_IS_UNION_INFO (base))
    {
      PyErr_SetString (PyExc_TypeError, "expected GIStructInfo or GIUnionInfo");
      return NULL;
    }

  PyObject *dict = PyDict_New ();
  if (dict == NULL)
    return NULL;

  const char *name = gi_base_info_get_name (base);
  const char *namespace_name = gi_base_info_get_namespace (base);
  const char *version
      = namespace_name ? gi_repository_get_version (ginext_shared_repository (), namespace_name)
                       : NULL;
  GType gtype = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)base);
  const char *type_name = g_type_name (gtype);
  size_t size = GI_IS_STRUCT_INFO (base) ? gi_struct_info_get_size ((GIStructInfo *)base)
                                         : gi_union_info_get_size ((GIUnionInfo *)base);

  PyObject *name_obj = PyUnicode_FromString (name ? name : "");
  PyObject *namespace_obj = PyUnicode_FromString (namespace_name ? namespace_name : "");
  PyObject *version_obj = PyUnicode_FromString (version ? version : "");
  PyObject *gtype_obj = PyLong_FromUnsignedLongLong ((unsigned long long)gtype);
  PyObject *type_name_obj = PyUnicode_FromString (type_name ? type_name : "");
  PyObject *size_obj = PyLong_FromSize_t (size);
  PyObject *kind_obj = PyUnicode_FromString (GI_IS_STRUCT_INFO (base) ? "record" : "union");
  if (name_obj == NULL || namespace_obj == NULL || version_obj == NULL || gtype_obj == NULL
      || type_name_obj == NULL || size_obj == NULL || kind_obj == NULL)
    goto error;
  if (PyDict_SetItemString (dict, "name", name_obj) < 0
      || PyDict_SetItemString (dict, "namespace", namespace_obj) < 0
      || PyDict_SetItemString (dict, "version", version_obj) < 0
      || PyDict_SetItemString (dict, "gtype", gtype_obj) < 0
      || PyDict_SetItemString (dict, "type_name", type_name_obj) < 0
      || PyDict_SetItemString (dict, "size", size_obj) < 0
      || PyDict_SetItemString (dict, "kind", kind_obj) < 0)
    goto error;
  Py_CLEAR (name_obj);
  Py_CLEAR (namespace_obj);
  Py_CLEAR (version_obj);
  Py_CLEAR (gtype_obj);
  Py_CLEAR (type_name_obj);
  Py_CLEAR (size_obj);
  Py_CLEAR (kind_obj);

  int n_methods = GI_IS_STRUCT_INFO (base) ? gi_struct_info_get_n_methods ((GIStructInfo *)base)
                                           : gi_union_info_get_n_methods ((GIUnionInfo *)base);
  PyObject *methods = PyList_New (n_methods);
  if (methods == NULL)
    goto error;
  for (int i = 0; i < n_methods; i++)
    {
      GIFunctionInfo *method = GI_IS_STRUCT_INFO (base)
                                   ? gi_struct_info_get_method ((GIStructInfo *)base, i)
                                   : gi_union_info_get_method ((GIUnionInfo *)base, i);
      PyObject *method_capsule = info_to_py_owned ((GIBaseInfo *)method);
      if (method_capsule == NULL)
        {
          Py_DECREF (methods);
          goto error;
        }
      PyList_SET_ITEM (methods, i, method_capsule);
    }
  if (PyDict_SetItemString (dict, "methods", methods) < 0)
    {
      Py_DECREF (methods);
      goto error;
    }
  Py_DECREF (methods);

  return dict;

error:
  Py_XDECREF (name_obj);
  Py_XDECREF (namespace_obj);
  Py_XDECREF (version_obj);
  Py_XDECREF (gtype_obj);
  Py_XDECREF (type_name_obj);
  Py_XDECREF (size_obj);
  Py_XDECREF (kind_obj);
  Py_DECREF (dict);
  return NULL;
}

/* StructInfo.find_method(name) / UnionInfo.find_method(name) — METH_VARARGS
 * method on both types; returns the FunctionInfo or None. */
PyObject *
ginext_find_method_method (PyObject *self, PyObject *args)
{
  const char *name = NULL;
  if (!PyArg_ParseTuple (args, "s", &name))
    return NULL;
  GIBaseInfo *base = PYGI_INFO (self);
  if (!GI_IS_STRUCT_INFO (base) && !GI_IS_UNION_INFO (base))
    {
      PyErr_SetString (PyExc_TypeError, "expected GIStructInfo or GIUnionInfo");
      return NULL;
    }

  GIFunctionInfo *method = GI_IS_STRUCT_INFO (base)
                               ? gi_struct_info_find_method ((GIStructInfo *)base, name)
                               : gi_union_info_find_method ((GIUnionInfo *)base, name);
  if (method == NULL)
    Py_RETURN_NONE;
  return info_to_py_owned ((GIBaseInfo *)method);
}

PyObject *
py_namespace_dir (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  const char *namespace_name = NULL;
  const char *version = NULL;
  if (!PyArg_ParseTuple (args, "ss", &namespace_name, &version))
    return NULL;

  GIRepository *repo = ginext_shared_repository ();
  if (repo == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "gi_repository_new failed");
      return NULL;
    }

  g_autoptr (GError) error = NULL;
  if (gi_repository_require (repo, namespace_name, version, GI_REPOSITORY_LOAD_FLAG_NONE, &error)
      == NULL)
    {
      PyErr_Format (PyExc_ImportError,
                    "gi_repository_require(%s, %s) failed: %s",
                    namespace_name,
                    version,
                    error && error->message ? error->message : "unknown error");
      return NULL;
    }

  unsigned int n_infos = gi_repository_get_n_infos (repo, namespace_name);
  PyObject *list = PyList_New ((Py_ssize_t)n_infos);
  if (list == NULL)
    return NULL;

  for (unsigned int i = 0; i < n_infos; i++)
    {
      g_autoptr (GIBaseInfo) info = gi_repository_get_info (repo, namespace_name, i);
      const char *name = info ? gi_base_info_get_name (info) : NULL;
      PyObject *item = PyUnicode_FromString (name ? name : "");
      if (item == NULL)
        {
          Py_DECREF (list);
          return NULL;
        }
      PyList_SET_ITEM (list, (Py_ssize_t)i, item);
    }

  return list;
}

PyObject *
py_namespace_is_registered (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  const char *namespace_name = NULL;
  PyObject *version_obj = Py_None;
  if (!PyArg_ParseTuple (args, "sO", &namespace_name, &version_obj))
    return NULL;

  const char *version = NULL;
  if (version_obj != Py_None)
    {
      if (!PyUnicode_Check (version_obj))
        {
          PyErr_SetString (PyExc_TypeError, "version must be a string or None");
          return NULL;
        }
      version = PyUnicode_AsUTF8 (version_obj);
      if (version == NULL)
        return NULL;
      if (version[0] == '\0')
        Py_RETURN_FALSE;
    }

  GIRepository *repo = ginext_shared_repository ();
  if (repo == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "gi_repository_new failed");
      return NULL;
    }

  gboolean registered = gi_repository_is_registered (repo, namespace_name, version);
  return PyBool_FromLong (registered ? 1 : 0);
}

static PyObject *
strv_to_list (const char *const *strv, gsize n)
{
  PyObject *list = PyList_New ((Py_ssize_t)n);
  if (list == NULL)
    return NULL;
  for (gsize i = 0; i < n; i++)
    {
      PyObject *s = PyUnicode_FromString (strv[i] ? strv[i] : "");
      if (s == NULL)
        {
          Py_DECREF (list);
          return NULL;
        }
      PyList_SET_ITEM (list, (Py_ssize_t)i, s);
    }
  return list;
}

PyObject *
py_namespace_get_dependencies (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  const char *namespace_name = NULL;
  if (!PyArg_ParseTuple (args, "s", &namespace_name))
    return NULL;

  GIRepository *repo = ginext_shared_repository ();
  if (repo == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "gi_repository_new failed");
      return NULL;
    }

  gsize n_deps = 0;
  char **deps = gi_repository_get_dependencies (repo, namespace_name, &n_deps);
  if (deps == NULL)
    return PyList_New (0);
  return strv_to_list ((const char *const *)deps, n_deps);
}

PyObject *
py_namespace_get_immediate_dependencies (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  const char *namespace_name = NULL;
  if (!PyArg_ParseTuple (args, "s", &namespace_name))
    return NULL;

  GIRepository *repo = ginext_shared_repository ();
  if (repo == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "gi_repository_new failed");
      return NULL;
    }

  gsize n_deps = 0;
  char **deps = gi_repository_get_immediate_dependencies (repo, namespace_name, &n_deps);
  if (deps == NULL)
    return PyList_New (0);
  return strv_to_list ((const char *const *)deps, n_deps);
}

PyObject *
pygi_object_info_by_gtype (GType lookup_gtype)
{
  GIRepository *repo = ginext_shared_repository ();
  if (repo == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "gi_repository_new failed");
      return NULL;
    }

  GIBaseInfo *info = gi_repository_find_by_gtype (repo, lookup_gtype);
  /* When a runtime type has no introspection of its own, walk its parent
   * class chain to find the nearest introspectable ancestor — but stop before
   * the generic G_TYPE_OBJECT. A private GObject subclass that derives from a
   * real introspectable type (e.g. a Gst element under GstElement) resolves to
   * that specific parent. But a private interface implementation (e.g.
   * GLocalFile under GFile) only reaches bare GObject by class-parent walking,
   * since the useful type is an *interface*, not a parent class. Resolving such
   * a type to GObject here would make the wrapper factory succeed with a bare
   * GObject.Object and suppress the C-level fallback to the static expected
   * type. Leaving info NULL at G_TYPE_OBJECT lets that fallback wrap the pointer
   * as the more specific interface (GFile). A type that genuinely *is* GObject
   * is matched directly above, before this walk. */
  if (info == NULL)
    {
      GType parent = g_type_parent (lookup_gtype);
      while (parent != G_TYPE_INVALID && parent != G_TYPE_NONE && parent != G_TYPE_OBJECT)
        {
          info = gi_repository_find_by_gtype (repo, parent);
          if (info != NULL)
            break;
          parent = g_type_parent (parent);
        }
    }
  if (info == NULL)
    {
      PyErr_Format (PyExc_AttributeError,
                    "no GI object info for GType %llu",
                    (unsigned long long)lookup_gtype);
      return NULL;
    }
  if (!GI_IS_OBJECT_INFO (info) && !GI_IS_INTERFACE_INFO (info))
    {
      gi_base_info_unref (info);
      PyErr_Format (PyExc_TypeError,
                    "GType %llu is not a GObject type or interface",
                    (unsigned long long)lookup_gtype);
      return NULL;
    }
  return info_to_py_owned (info);
}

PyObject *
py_object_info_by_gtype (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  unsigned long long gtype_arg = 0;
  if (!PyArg_ParseTuple (args, "K", &gtype_arg))
    return NULL;
  return pygi_object_info_by_gtype ((GType)gtype_arg);
}

/* namespace_find_by_gtype(gtype_int) -> (namespace, name) | None
 *
 * Look up any registered GI type (object, interface, enum, flags, struct,
 * union) by its GType integer.  Returns a (namespace, name) tuple on success,
 * or None if the GType is not registered in the introspection data.
 */
PyObject *
py_namespace_find_by_gtype (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  unsigned long long gtype_arg = 0;
  if (!PyArg_ParseTuple (args, "K", &gtype_arg))
    return NULL;
  GType gtype = (GType)gtype_arg;

  GIRepository *repo = ginext_shared_repository ();
  if (repo == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "gi_repository_new failed");
      return NULL;
    }

  GIBaseInfo *info = gi_repository_find_by_gtype (repo, gtype);
  if (info == NULL)
    Py_RETURN_NONE;

  const char *ns = gi_base_info_get_namespace (info);
  const char *name = gi_base_info_get_name (info);
  PyObject *result = Py_BuildValue ("(ss)", ns, name);
  gi_base_info_unref (info);
  return result;
}

/* ObjectInfo.object_info() / InterfaceInfo.object_info() — build the metadata
 * dict the class builder consumes. Registered as a METH_NOARGS method on both
 * types (self is the GIObjectInfo or GIInterfaceInfo). */
PyObject *
ginext_object_info_method (PyObject *self, PyObject *Py_UNUSED (args))
{
  GIBaseInfo *base = PYGI_INFO (self);
  if (!GI_IS_OBJECT_INFO (base) && !GI_IS_INTERFACE_INFO (base))
    {
      PyErr_SetString (PyExc_TypeError, "expected GIObjectInfo or GIInterfaceInfo");
      return NULL;
    }

  GIObjectInfo *object_info = GI_IS_OBJECT_INFO (base) ? (GIObjectInfo *)base : NULL;
  GIInterfaceInfo *interface_info = GI_IS_INTERFACE_INFO (base) ? (GIInterfaceInfo *)base : NULL;
  PyObject *dict = PyDict_New ();
  if (dict == NULL)
    return NULL;

  const char *name = gi_base_info_get_name (base);
  const char *namespace_name = gi_base_info_get_namespace (base);
  GType gtype = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)base);
  PyObject *name_obj = PyUnicode_FromString (name ? name : "");
  if (name_obj == NULL)
    goto error;
  if (PyDict_SetItemString (dict, "name", name_obj) < 0)
    {
      Py_DECREF (name_obj);
      goto error;
    }
  Py_DECREF (name_obj);

  PyObject *namespace_obj = PyUnicode_FromString (namespace_name ? namespace_name : "");
  if (namespace_obj == NULL)
    goto error;
  if (PyDict_SetItemString (dict, "namespace", namespace_obj) < 0)
    {
      Py_DECREF (namespace_obj);
      goto error;
    }
  Py_DECREF (namespace_obj);

  const char *version
      = namespace_name ? gi_repository_get_version (ginext_shared_repository (), namespace_name)
                       : NULL;
  PyObject *version_obj = PyUnicode_FromString (version ? version : "");
  if (version_obj == NULL)
    goto error;
  if (PyDict_SetItemString (dict, "version", version_obj) < 0)
    {
      Py_DECREF (version_obj);
      goto error;
    }
  Py_DECREF (version_obj);

  PyObject *gtype_obj = PyLong_FromUnsignedLongLong ((unsigned long long)gtype);
  if (gtype_obj == NULL)
    goto error;
  if (PyDict_SetItemString (dict, "gtype", gtype_obj) < 0)
    {
      Py_DECREF (gtype_obj);
      goto error;
    }
  Py_DECREF (gtype_obj);

  PyObject *is_gobject_obj
      = PyBool_FromLong (gtype != G_TYPE_INVALID && g_type_is_a (gtype, G_TYPE_OBJECT));
  if (is_gobject_obj == NULL)
    goto error;
  if (PyDict_SetItemString (dict, "is_gobject", is_gobject_obj) < 0)
    {
      Py_DECREF (is_gobject_obj);
      goto error;
    }
  Py_DECREF (is_gobject_obj);

  PyObject *is_instantiatable_obj
      = PyBool_FromLong (gtype != G_TYPE_INVALID && G_TYPE_IS_INSTANTIATABLE (gtype));
  if (is_instantiatable_obj == NULL)
    goto error;
  if (PyDict_SetItemString (dict, "is_instantiatable", is_instantiatable_obj) < 0)
    {
      Py_DECREF (is_instantiatable_obj);
      goto error;
    }
  Py_DECREF (is_instantiatable_obj);

  const char *type_name = g_type_name (gtype);
  PyObject *type_name_obj = PyUnicode_FromString (type_name ? type_name : "");
  if (type_name_obj == NULL)
    goto error;
  if (PyDict_SetItemString (dict, "type_name", type_name_obj) < 0)
    {
      Py_DECREF (type_name_obj);
      goto error;
    }
  Py_DECREF (type_name_obj);

  GIObjectInfo *parent = object_info != NULL ? gi_object_info_get_parent (object_info) : NULL;
  PyObject *parent_obj = parent ? info_to_py_owned ((GIBaseInfo *)parent) : Py_NewRef (Py_None);
  if (parent_obj == NULL)
    goto error;
  if (PyDict_SetItemString (dict, "parent", parent_obj) < 0)
    {
      Py_DECREF (parent_obj);
      goto error;
    }
  Py_DECREF (parent_obj);

  GIBaseInfo *class_struct = NULL;
  if (object_info != NULL)
    class_struct = (GIBaseInfo *)gi_object_info_get_class_struct (object_info);
  PyObject *class_struct_obj = class_struct ? info_to_py_owned (class_struct) : Py_NewRef (Py_None);
  if (class_struct_obj == NULL)
    goto error;
  if (PyDict_SetItemString (dict, "class_struct", class_struct_obj) < 0)
    {
      Py_DECREF (class_struct_obj);
      goto error;
    }
  Py_DECREF (class_struct_obj);

  PyObject *interfaces = NULL;
  if (object_info != NULL)
    {
      int n_interfaces = (int)gi_object_info_get_n_interfaces (object_info);
      interfaces = PyList_New (n_interfaces);
      if (interfaces == NULL)
        goto error;
      for (int i = 0; i < n_interfaces; i++)
        {
          GIInterfaceInfo *iface = gi_object_info_get_interface (object_info, i);
          PyObject *iface_capsule = info_to_py_owned ((GIBaseInfo *)iface);
          if (iface_capsule == NULL)
            {
              Py_DECREF (interfaces);
              goto error;
            }
          PyList_SET_ITEM (interfaces, i, iface_capsule);
        }
    }
  else
    {
      interfaces = PyList_New (0);
      if (interfaces == NULL)
        goto error;
    }
  if (PyDict_SetItemString (dict, "interfaces", interfaces) < 0)
    {
      Py_DECREF (interfaces);
      goto error;
    }
  Py_DECREF (interfaces);

  int n_properties = object_info != NULL ? (int)gi_object_info_get_n_properties (object_info)
                                         : (int)gi_interface_info_get_n_properties (interface_info);
  PyObject *properties = PyList_New (n_properties);
  if (properties == NULL)
    goto error;
  for (int i = 0; i < n_properties; i++)
    {
      GIPropertyInfo *property = object_info != NULL
                                     ? gi_object_info_get_property (object_info, i)
                                     : gi_interface_info_get_property (interface_info, i);
      PyObject *property_capsule = info_to_py_owned ((GIBaseInfo *)property);
      if (property_capsule == NULL)
        {
          Py_DECREF (properties);
          goto error;
        }
      PyList_SET_ITEM (properties, i, property_capsule);
    }
  if (PyDict_SetItemString (dict, "properties", properties) < 0)
    {
      Py_DECREF (properties);
      goto error;
    }
  Py_DECREF (properties);

  int n_methods = object_info != NULL ? (int)gi_object_info_get_n_methods (object_info)
                                      : (int)gi_interface_info_get_n_methods (interface_info);
  PyObject *methods = PyList_New (n_methods);
  if (methods == NULL)
    goto error;
  for (int i = 0; i < n_methods; i++)
    {
      GIFunctionInfo *method = object_info != NULL
                                   ? gi_object_info_get_method (object_info, i)
                                   : gi_interface_info_get_method (interface_info, i);
      PyObject *method_capsule = info_to_py_owned ((GIBaseInfo *)method);
      if (method_capsule == NULL)
        {
          Py_DECREF (methods);
          goto error;
        }
      PyList_SET_ITEM (methods, i, method_capsule);
    }
  if (PyDict_SetItemString (dict, "methods", methods) < 0)
    {
      Py_DECREF (methods);
      goto error;
    }
  Py_DECREF (methods);

  int n_signals = object_info != NULL ? (int)gi_object_info_get_n_signals (object_info)
                                      : (int)gi_interface_info_get_n_signals (interface_info);
  PyObject *signals = PyList_New (n_signals);
  if (signals == NULL)
    goto error;
  for (int i = 0; i < n_signals; i++)
    {
      GISignalInfo *signal = object_info != NULL ? gi_object_info_get_signal (object_info, i)
                                                 : gi_interface_info_get_signal (interface_info, i);
      PyObject *signal_capsule = info_to_py_owned ((GIBaseInfo *)signal);
      if (signal_capsule == NULL)
        {
          Py_DECREF (signals);
          goto error;
        }
      PyList_SET_ITEM (signals, i, signal_capsule);
    }
  if (PyDict_SetItemString (dict, "signals", signals) < 0)
    {
      Py_DECREF (signals);
      goto error;
    }
  Py_DECREF (signals);

  int n_vfuncs = object_info != NULL ? (int)gi_object_info_get_n_vfuncs (object_info)
                                     : (int)gi_interface_info_get_n_vfuncs (interface_info);
  PyObject *vfuncs = PyList_New (n_vfuncs);
  if (vfuncs == NULL)
    goto error;
  for (int i = 0; i < n_vfuncs; i++)
    {
      GIVFuncInfo *vfunc = object_info != NULL ? gi_object_info_get_vfunc (object_info, i)
                                               : gi_interface_info_get_vfunc (interface_info, i);
      PyObject *vfunc_capsule = info_to_py_owned ((GIBaseInfo *)vfunc);
      if (vfunc_capsule == NULL)
        {
          Py_DECREF (vfuncs);
          goto error;
        }
      PyList_SET_ITEM (vfuncs, i, vfunc_capsule);
    }
  if (PyDict_SetItemString (dict, "vfuncs", vfuncs) < 0)
    {
      Py_DECREF (vfuncs);
      goto error;
    }
  Py_DECREF (vfuncs);

  return dict;

error:
  Py_DECREF (dict);
  return NULL;
}

PyObject *
ginext_callable_info_arg_names (GICallableInfo *callable)
{
  int n_args = gi_callable_info_get_n_args (callable);
  gboolean *skip = g_new0 (gboolean, n_args > 0 ? (gsize)n_args : 1);
  for (int i = 0; i < n_args; i++)
    {
      g_autoptr (GIArgInfo) arg_info = gi_callable_info_get_arg (callable, i);
      if (gi_arg_info_get_direction (arg_info) == GI_DIRECTION_OUT)
        {
          skip[i] = TRUE;
          continue;
        }

      g_autoptr (GITypeInfo) type_info = gi_arg_info_get_type_info (arg_info);
      if (gi_type_info_get_tag (type_info) == GI_TYPE_TAG_ARRAY)
        {
          unsigned int length_index = 0;
          if (gi_type_info_get_array_length_index (type_info, &length_index)
              && length_index < (unsigned int)n_args)
            skip[length_index] = TRUE;
        }

      unsigned int closure_index = 0;
      if (gi_arg_info_get_closure_index (arg_info, &closure_index)
          && closure_index < (unsigned int)n_args && closure_index != (unsigned int)i)
        skip[closure_index] = TRUE;

      unsigned int destroy_index = 0;
      /* Forward-only: some GIRs (GLib.log_set_writer_func) place a
       * destroy="<callback-index>" back-pointer on the destroy_notify
       * arg itself. Following it from the back-pointer source would
       * hide the callback. The forward source (the callback) always
       * points forward. */
      if (gi_arg_info_get_destroy_index (arg_info, &destroy_index)
          && destroy_index < (unsigned int)n_args && destroy_index > (unsigned int)i)
        skip[destroy_index] = TRUE;
    }

  int n_visible = 0;
  for (int i = 0; i < n_args; i++)
    {
      if (!skip[i])
        n_visible++;
    }

  PyObject *names = PyList_New (n_visible);
  if (names == NULL)
    {
      g_free (skip);
      return NULL;
    }
  int visible = 0;
  for (int i = 0; i < n_args; i++)
    {
      if (skip[i])
        continue;
      g_autoptr (GIArgInfo) arg_info = gi_callable_info_get_arg (callable, i);
      const char *name = gi_base_info_get_name ((GIBaseInfo *)arg_info);
      PyObject *py_name = PyUnicode_FromString (name ? name : "");
      if (py_name == NULL)
        {
          Py_DECREF (names);
          g_free (skip);
          return NULL;
        }
      PyList_SET_ITEM (names, visible++, py_name);
    }
  g_free (skip);
  return names;
}

PyObject *
py_callable_arg_names (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *capsule = NULL;
  if (!PyArg_ParseTuple (args, "O", &capsule))
    return NULL;
  GIBaseInfo *info = info_from_capsule (capsule);
  if (info == NULL)
    return NULL;
  if (!GI_IS_CALLABLE_INFO (info))
    {
      PyErr_SetString (PyExc_TypeError, "expected GICallableInfo capsule");
      return NULL;
    }
  return ginext_callable_info_arg_names ((GICallableInfo *)info);
}

/* True iff the callable has a callback arg whose `closure` annotation
 * points at a user_data slot. Used by method.py to gate pygobject-style
 * user_data carving (trailing positionals → user_data tuple) so plain
 * functions still surface "takes N args (M given)" on legitimate
 * over-passing. */
PyObject *
ginext_callable_info_has_user_data_slot (GICallableInfo *callable)
{
  int n_args = gi_callable_info_get_n_args (callable);
  for (int i = 0; i < n_args; i++)
    {
      g_autoptr (GIArgInfo) arg_info = gi_callable_info_get_arg (callable, i);
      unsigned int closure_idx = 0;
      if (gi_arg_info_get_closure_index (arg_info, &closure_idx) && (int)closure_idx < n_args
          && (int)closure_idx != i)
        Py_RETURN_TRUE;
    }
  Py_RETURN_FALSE;
}

PyObject *
py_callable_has_user_data_slot (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *capsule = NULL;
  if (!PyArg_ParseTuple (args, "O", &capsule))
    return NULL;
  GIBaseInfo *info = info_from_capsule (capsule);
  if (info == NULL)
    return NULL;
  if (!GI_IS_CALLABLE_INFO (info))
    {
      PyErr_SetString (PyExc_TypeError, "expected GICallableInfo capsule");
      return NULL;
    }
  return ginext_callable_info_has_user_data_slot ((GICallableInfo *)info);
}

/* For an async GIR method, return (finish_func_name, callback_position) where
 * callback_position is the Python-visible (skip-aware) index of the
 * AsyncReadyCallback argument. `finish_func_name` is "" when the typelib does
 * not record the finish function (the caller then applies the *_async ->
 * *_finish naming convention). Returns None when no async-ready callback
 * argument is present. Drives ginext.aio's AsyncCallable wrapping. */
PyObject *
py_callable_async_info (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *capsule = NULL;
  if (!PyArg_ParseTuple (args, "O", &capsule))
    return NULL;
  GIBaseInfo *info = info_from_capsule (capsule);
  if (info == NULL)
    return NULL;
  if (!GI_IS_CALLABLE_INFO (info))
    {
      PyErr_SetString (PyExc_TypeError, "expected GICallableInfo capsule");
      return NULL;
    }
  GICallableInfo *callable = (GICallableInfo *)info;

  /* The callback position must match the Python-visible argument order, so
   * apply the same skip rules as ginext_callable_info_arg_names (OUT params,
   * array-length back-pointers, and closure/destroy user_data slots are
   * hidden). The AsyncReadyCallback is found by GI_SCOPE_TYPE_ASYNC, falling
   * back to "the (single) callback-typed argument" for GIRs that omit the
   * async scope annotation (e.g. GdkPixbuf). */
  int n_args = gi_callable_info_get_n_args (callable);
  gboolean *skip = g_new0 (gboolean, n_args > 0 ? (gsize)n_args : 1);
  int cb_index = -1;
  int callback_typed_index = -1;
  for (int i = 0; i < n_args; i++)
    {
      g_autoptr (GIArgInfo) arg_info = gi_callable_info_get_arg (callable, i);
      if (gi_arg_info_get_direction (arg_info) == GI_DIRECTION_OUT)
        {
          skip[i] = TRUE;
          continue;
        }
      g_autoptr (GITypeInfo) type_info = gi_arg_info_get_type_info (arg_info);
      if (gi_type_info_get_tag (type_info) == GI_TYPE_TAG_ARRAY)
        {
          unsigned int length_index = 0;
          if (gi_type_info_get_array_length_index (type_info, &length_index)
              && length_index < (unsigned int)n_args)
            skip[length_index] = TRUE;
        }
      else if (gi_type_info_get_tag (type_info) == GI_TYPE_TAG_INTERFACE)
        {
          g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (type_info);
          if (iface != NULL && GI_IS_CALLBACK_INFO (iface))
            callback_typed_index = i;
        }
      unsigned int closure_index = 0;
      if (gi_arg_info_get_closure_index (arg_info, &closure_index)
          && closure_index < (unsigned int)n_args && closure_index != (unsigned int)i)
        skip[closure_index] = TRUE;
      unsigned int destroy_index = 0;
      if (gi_arg_info_get_destroy_index (arg_info, &destroy_index)
          && destroy_index < (unsigned int)n_args && destroy_index > (unsigned int)i)
        skip[destroy_index] = TRUE;
      if (gi_arg_info_get_scope (arg_info) == GI_SCOPE_TYPE_ASYNC)
        cb_index = i;
    }
  if (cb_index < 0)
    cb_index = callback_typed_index;
  if (cb_index < 0)
    {
      g_free (skip);
      Py_RETURN_NONE;
    }

  GICallableInfo *finish = gi_callable_info_get_finish_function (callable);
  const char *finish_name = finish != NULL ? gi_base_info_get_name ((GIBaseInfo *)finish) : "";

  int visible = 0;
  for (int i = 0; i < cb_index; i++)
    {
      if (!skip[i])
        visible++;
    }
  int cb_position = visible;
  g_free (skip);

  PyObject *result = Py_BuildValue ("(si)", finish_name ? finish_name : "", cb_position);
  if (finish != NULL)
    gi_base_info_unref ((GIBaseInfo *)finish);
  return result;
}

PyObject *
py_reset_invoke_stats (PyObject *module G_GNUC_UNUSED, PyObject *Py_UNUSED (args))
{
  invoke_plan_gi_metadata_calls = 0;
  invoke_hot_gi_metadata_calls = 0;
  Py_RETURN_NONE;
}

PyObject *
py_invoke_stats (PyObject *module G_GNUC_UNUSED, PyObject *Py_UNUSED (args))
{
  return Py_BuildValue ("{sK,sK}",
                        "plan_gi_metadata_calls",
                        invoke_plan_gi_metadata_calls,
                        "invoke_gi_metadata_calls",
                        invoke_hot_gi_metadata_calls);
}
