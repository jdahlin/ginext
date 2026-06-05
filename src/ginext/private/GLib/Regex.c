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

/* Regex.c - accept a Python re.Pattern wherever GLib expects a GRegex. A
 * re.Pattern handed to a GRegex-typed argument or GObject property is compiled
 * into a GRegex on demand; GRegex values coming back out stay GLib.Regex. Only
 * the compile flags are translated; the pattern source string is passed through
 * unchanged (PCRE2 vs Python sre syntax differences are the caller's
 * responsibility). */
#include "GLib/Regex.h"

/* re module singletons, resolved once. Owned references kept for the lifetime
 * of the process (module-level singletons). */
static PyObject *re_pattern_type = NULL;

/* re.RegexFlag bits we map; resolved from the live re module so we never bake
 * CPython's sre flag values into C. */
static long re_flag_ignorecase = 0;
static long re_flag_multiline = 0;
static long re_flag_dotall = 0;
static long re_flag_verbose = 0;

static int re_init_state = 0; /* 0=unattempted, 1=ready, -1=failed */
static GMutex re_init_lock;

static long
fetch_flag (PyObject *re_mod, const char *name)
{
  PyObject *attr = PyObject_GetAttrString (re_mod, name);
  if (attr == NULL)
    return -1;
  long value = PyLong_AsLong (attr);
  Py_DECREF (attr);
  return value;
}

/* Ensure the re module singletons are cached. Returns 1 on success, 0 on
 * failure (Python error set). */
static int
ensure_re_init (void)
{
  g_mutex_lock (&re_init_lock);
  if (re_init_state == 0)
    {
      re_init_state = -1; /* assume failure until everything resolves */
      PyObject *re_mod = PyImport_ImportModule ("re");
      if (re_mod != NULL)
        {
          PyObject *pattern_type = PyObject_GetAttrString (re_mod, "Pattern");
          re_flag_ignorecase = fetch_flag (re_mod, "IGNORECASE");
          re_flag_multiline = fetch_flag (re_mod, "MULTILINE");
          re_flag_dotall = fetch_flag (re_mod, "DOTALL");
          re_flag_verbose = fetch_flag (re_mod, "VERBOSE");
          if (pattern_type != NULL && !PyErr_Occurred ())
            {
              re_pattern_type = pattern_type; /* steal ref */
              re_init_state = 1;
            }
          else
            {
              Py_XDECREF (pattern_type);
            }
          Py_DECREF (re_mod);
        }
    }
  int state = re_init_state;
  g_mutex_unlock (&re_init_lock);
  if (state != 1 && !PyErr_Occurred ())
    PyErr_SetString (PyExc_RuntimeError, "could not initialize the re module");
  return state == 1 ? 1 : 0;
}

int
pygi_is_re_pattern (PyObject *obj)
{
  if (obj == NULL)
    return 0;
  if (!ensure_re_init ())
    {
      PyErr_Clear ();
      return 0;
    }
  return PyObject_TypeCheck (obj, (PyTypeObject *)re_pattern_type) ? 1 : 0;
}

static GRegexCompileFlags
reflags_to_gflags (long flags)
{
  GRegexCompileFlags out = 0;
  if (flags & re_flag_ignorecase)
    out |= G_REGEX_CASELESS;
  if (flags & re_flag_multiline)
    out |= G_REGEX_MULTILINE;
  if (flags & re_flag_dotall)
    out |= G_REGEX_DOTALL;
  if (flags & re_flag_verbose)
    out |= G_REGEX_EXTENDED;
  /* re.UNICODE/ASCII/LOCALE/DEBUG have no GRegex compile-flag equivalent and
   * are dropped: PCRE2 is Unicode-aware by default, so RAW must stay off. */
  return out;
}

GRegex *
pygi_gregex_from_py_pattern (PyObject *pattern)
{
  if (!ensure_re_init ())
    return NULL;
  if (!PyObject_TypeCheck (pattern, (PyTypeObject *)re_pattern_type))
    {
      PyErr_Format (PyExc_TypeError,
                    "expected a re.Pattern, not %.200s",
                    Py_TYPE (pattern)->tp_name);
      return NULL;
    }

  PyObject *src = PyObject_GetAttrString (pattern, "pattern");
  if (src == NULL)
    return NULL;
  if (!PyUnicode_Check (src))
    {
      Py_DECREF (src);
      PyErr_SetString (PyExc_TypeError,
                       "only str (not bytes) re.Pattern objects map to GLib.Regex");
      return NULL;
    }
  const char *pattern_str = PyUnicode_AsUTF8 (src);
  if (pattern_str == NULL)
    {
      Py_DECREF (src);
      return NULL;
    }

  long flags = 0;
  PyObject *py_flags = PyObject_GetAttrString (pattern, "flags");
  if (py_flags != NULL)
    {
      flags = PyLong_AsLong (py_flags);
      Py_DECREF (py_flags);
    }
  if (PyErr_Occurred ())
    {
      Py_DECREF (src);
      return NULL;
    }

  GError *error = NULL;
  GRegex *regex = g_regex_new (pattern_str, reflags_to_gflags (flags), 0, &error);
  Py_DECREF (src);
  if (regex == NULL)
    {
      PyErr_Format (PyExc_ValueError,
                    "GLib.Regex cannot compile this pattern: %s",
                    error != NULL ? error->message : "unknown error");
      if (error != NULL)
        g_error_free (error);
      return NULL;
    }
  return regex;
}
