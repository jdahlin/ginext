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

/* Variant.c - minimal GVariant marshalling for ginext invoke paths. */
#include "GLib/Variant.h"

#include "GObject/Boxed.h"
#include "runtime/class-registry.h"

int
pygi_variant_from_py (PyObject *value, GIArgument *out)
{
  g_return_val_if_fail (out != NULL, -1);

  if (value == Py_None)
    {
      out->v_pointer = NULL;
      return 0;
    }

  if (pygi_boxed_check (value))
    {
      PyGIGLibBoxed *boxed = (PyGIGLibBoxed *)value;
      if (boxed->gtype != G_TYPE_VARIANT)
        {
          PyErr_SetString (PyExc_TypeError, "GVariant argument must be GLib.Variant");
          return -1;
        }
      out->v_pointer = boxed->boxed != NULL ? g_variant_ref ((GVariant *)boxed->boxed) : NULL;
      return 0;
    }
  PyErr_Clear ();

  if (!PyUnicode_Check (value))
    {
      PyErr_SetString (PyExc_TypeError,
                       "GVariant argument must be GLib.Variant, a string, or None");
      return -1;
    }

  const char *text = PyUnicode_AsUTF8 (value);
  if (text == NULL)
    return -1;

  g_autoptr (GError) error = NULL;
  GVariant *variant = g_variant_parse (NULL, text, NULL, NULL, &error);
  if (variant == NULL)
    {
      PyErr_Format (PyExc_ValueError,
                    "invalid GVariant text: %s",
                    error != NULL && error->message != NULL ? error->message : "unknown error");
      return -1;
    }

  out->v_pointer = g_variant_ref_sink (variant);
  return 0;
}

PyObject *
pygi_variant_to_py (GITypeInfo *ti, GIArgument *arg, GITransfer transfer)
{
  (void)ti;
  g_return_val_if_fail (arg != NULL, NULL);

  GVariant *variant = (GVariant *)arg->v_pointer;
  if (variant == NULL)
    Py_RETURN_NONE;

  PyObject *cls = pygi_class_registry_get_pytype_for_gtype (G_TYPE_VARIANT);
  if (cls == NULL)
    {
      g_autofree char *text = g_variant_print (variant, TRUE);
      PyObject *py = text != NULL ? PyUnicode_FromString (text) : PyErr_NoMemory ();
      if (transfer != GI_TRANSFER_NOTHING)
        g_variant_unref (variant);
      return py;
    }

  if (transfer == GI_TRANSFER_NOTHING)
    variant = g_variant_ref (variant);

  return pygi_boxed_new (cls, variant, G_TYPE_VARIANT, 1);
}

PyObject *
pygi_wrap_variant (GITypeInfo *ti, GVariant *variant, GITransfer transfer)
{
  GIArgument arg = { .v_pointer = variant };
  return pygi_variant_to_py (ti, &arg, transfer);
}

int
pygi_py_item_to_gvariant (PyObject *item, void **dst)
{
  g_return_val_if_fail (dst != NULL, -1);

  GIArgument arg = { 0 };
  if (pygi_variant_from_py (item, &arg) != 0)
    return -1;

  *dst = arg.v_pointer;
  return 0;
}
