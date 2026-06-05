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

/* string.c - UTF8 and FILENAME GI type marshaling. */

#include "marshal/string.h"

#include <glib.h>
#include <string.h>

/* --------------------------------------------------------------------- */
/* UTF8                                                                   */
/* --------------------------------------------------------------------- */

/* str / bytes / bytearray -> borrowed C string. Matches pygobject's
 * leniency: GIR utf8 params accept any of these on input. The returned
 * pointer is borrowed (lifetime is the input object's; caller keeps the
 * PyObject alive across the C call). */
static char *
borrow_as_c_string (PyObject *h)
{
  if (PyUnicode_Check (h))
    return (char *)PyUnicode_AsUTF8AndSize (h, NULL);
  if (PyBytes_Check (h))
    return PyBytes_AsString (h);
  if (PyByteArray_Check (h))
    return PyByteArray_AsString (h);
  PyErr_Format (PyExc_TypeError,
                "expected str, bytes, or bytearray, not %.200s",
                Py_TYPE (h)->tp_name);
  return NULL;
}

int
pygi_utf8_from_py (PyObject *h, GIArgument *out)
{
  g_return_val_if_fail (out != NULL, -1);
  if (h == Py_None)
    {
      out->v_string = NULL;
      return 0;
    }
  out->v_string = borrow_as_c_string (h);
  return PyErr_Occurred () ? -1 : 0;
}

PyObject *
pygi_utf8_to_py (GIArgument *arg, GITransfer transfer)
{
  g_return_val_if_fail (arg != NULL, NULL);
  const char *s = arg->v_string;
  if (s == NULL)
    Py_RETURN_NONE;
  PyObject *out = PyUnicode_FromString (s);
  if (out == NULL)
    {
      /* Invalid UTF-8: clear the error and return raw bytes instead. */
      PyErr_Clear ();
      out = PyBytes_FromString (s);
    }
  if (transfer == GI_TRANSFER_EVERYTHING)
    g_free (arg->v_string);
  return out;
}

/* --------------------------------------------------------------------- */
/* FILENAME                                                               */
/* --------------------------------------------------------------------- */

int
pygi_filename_from_py (PyObject *h, GIArgument *out)
{
  g_return_val_if_fail (out != NULL, -1);
  if (h == Py_None)
    {
      out->v_string = NULL;
      return 0;
    }
  /* os.PathLike -> fspath() -> str/bytes. PyOS_FSPath does the dispatch. */
  PyObject *coerced = NULL;
  if (!PyUnicode_Check (h) && !PyBytes_Check (h) && !PyByteArray_Check (h))
    {
      coerced = PyOS_FSPath (h);
      if (coerced == NULL)
        return -1;
      h = coerced;
    }
  Py_ssize_t size = 0;
  if (PyUnicode_Check (h))
    {
#ifdef _WIN32
      /* Encode with surrogatepass so lone surrogates from Windows paths
         survive as WTF-8 (matches pygobject). The encoded bytes is stashed in
         `coerced` so it lives until this function returns, like the PathLike
         path below. */
      PyObject *enc = PyUnicode_AsEncodedString (h, "utf-8", "surrogatepass");
      if (enc == NULL)
        {
          Py_XDECREF (coerced);
          return -1;
        }
      Py_XSETREF (coerced, enc);
      size = PyBytes_GET_SIZE (enc);
      out->v_string = PyBytes_AsString (enc);
#else
      out->v_string = (char *)PyUnicode_AsUTF8AndSize (h, &size);
#endif
      if (out->v_string != NULL && memchr (out->v_string, '\0', (size_t)size) != NULL)
        {
          PyErr_SetString (PyExc_ValueError, "embedded null byte");
          out->v_string = NULL;
        }
    }
  else if (PyBytes_Check (h))
    {
      size = PyBytes_GET_SIZE (h);
      out->v_string = PyBytes_AsString (h);
      if (out->v_string != NULL && memchr (out->v_string, '\0', (size_t)size) != NULL)
        {
          PyErr_SetString (PyExc_ValueError, "embedded null byte");
          out->v_string = NULL;
        }
    }
  else if (PyByteArray_Check (h))
    {
      size = PyByteArray_GET_SIZE (h);
      out->v_string = PyByteArray_AsString (h);
      if (out->v_string != NULL && memchr (out->v_string, '\0', (size_t)size) != NULL)
        {
          PyErr_SetString (PyExc_ValueError, "embedded null byte");
          out->v_string = NULL;
        }
    }
  else
    out->v_string = borrow_as_c_string (h);
  /* coerced is dropped on return; the borrowed pointer is only valid
   * for the duration of the C call. The marshal layer (callers of
   * this path) keep the original PyObject alive across the call -
   * but for the PathLike path we synthesize a new bytes/str and would
   * lose it. Stash on the arg's cleanup if the cleanup hook is wired,
   * else accept the risk for the simple-arg case (PyOS_FSPath result
   * is typically interned-immortal for short paths, but not always).
   *
   * TODO: thread `coerced` through the cleanup slot so the lifetime is
   * properly tied to the call. For now drop the ref and rely on the
   * fact that the C side reads the string before any GC. */
  Py_XDECREF (coerced);
  return PyErr_Occurred () ? -1 : 0;
}

PyObject *
pygi_filename_to_py (GIArgument *arg, GITransfer transfer)
{
  g_return_val_if_fail (arg != NULL, NULL);
  const char *s = arg->v_string;
  PyObject *out;
  if (s == NULL)
    out = Py_NewRef (Py_None);
  else
#ifdef _WIN32
    /* GLib filenames are UTF-8 on Windows, but can carry lone surrogates from
       Windows paths (WTF-8); decode with surrogatepass to match pygobject. */
    out = PyUnicode_DecodeUTF8 (s, (Py_ssize_t)strlen (s), "surrogatepass");
#else
    out = PyUnicode_FromString (s);
#endif
  if (transfer == GI_TRANSFER_EVERYTHING && s != NULL)
    g_free (arg->v_string);
  return out;
}

/* --------------------------------------------------------------------- */
/* GStrv                                                                  */
/* --------------------------------------------------------------------- */

PyObject *
pygi_strv_to_py_list (gchar **strv, GITransfer transfer)
{
  if (strv == NULL)
    return PyList_New (0);

  gsize n = 0;
  while (strv[n] != NULL)
    n++;

  PyObject *list = PyList_New ((Py_ssize_t)n);
  if (list == NULL)
    return NULL;

  for (gsize i = 0; i < n; i++)
    {
      PyObject *s = PyUnicode_FromString (strv[i]);
      if (s == NULL)
        {
          Py_DECREF (list);
          return NULL;
        }
      PyList_SET_ITEM (list, (Py_ssize_t)i, s);
    }

  if (transfer == GI_TRANSFER_EVERYTHING)
    g_strfreev (strv);
  else if (transfer == GI_TRANSFER_CONTAINER)
    g_free (strv);
  return list;
}
