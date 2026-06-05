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

#include "cairo/foreign.h"

#include "cairo/foreign-internal.h"

int
pygi_foreign_cairo_from_py (PyObject *value, GIBaseInfo *iface, GITransfer transfer, GIArgument *out)
{
  const PyGICairoCAPI *capi;

  if (value == Py_None)
    {
      out->v_pointer = NULL;
      return 0;
    }

  capi = lookup_pycairo_capi ();

  CAIRO_FROM_PY_REFCOUNTED ("Context",
                            Context_Type,
                            PyGICairoContext,
                            ctx,
                            cairo_t *,
                            "Context",
                            lookup_cairo_reference,
                            "cairo_reference unavailable")
  CAIRO_FROM_PY_REFCOUNTED ("Surface",
                            Surface_Type,
                            PyGICairoSurface,
                            surface,
                            cairo_surface_t *,
                            "Surface",
                            lookup_cairo_surface_reference,
                            "cairo_surface_reference unavailable")
  CAIRO_FROM_PY_REFCOUNTED ("FontFace",
                            FontFace_Type,
                            PyGICairoFontFace,
                            font_face,
                            cairo_font_face_t *,
                            "FontFace",
                            lookup_cairo_font_face_reference,
                            "cairo_font_face_reference unavailable")
  CAIRO_FROM_PY_REFCOUNTED ("ScaledFont",
                            ScaledFont_Type,
                            PyGICairoScaledFont,
                            scaled_font,
                            cairo_scaled_font_t *,
                            "ScaledFont",
                            lookup_cairo_scaled_font_reference,
                            "cairo_scaled_font_reference unavailable")
  CAIRO_FROM_PY_REFCOUNTED ("Pattern",
                            Pattern_Type,
                            PyGICairoPattern,
                            pattern,
                            cairo_pattern_t *,
                            "Pattern",
                            lookup_cairo_pattern_reference,
                            "cairo_pattern_reference unavailable")
  CAIRO_FROM_PY_REFCOUNTED ("Region",
                            Region_Type,
                            PyGICairoRegion,
                            region,
                            cairo_region_t *,
                            "Region",
                            lookup_cairo_region_reference,
                            "cairo_region_reference unavailable")

  if (is_cairo_info (iface, "Path"))
    {
      cairo_path_t *path;

      if (ensure_cairo_capi (capi) != 0)
        return -1;
      if (!PyObject_TypeCheck (value, capi->Path_Type))
        return raise_expected_cairo_type ("Path");
      path = ((PyGICairoPath *)value)->path;
      if (path == NULL)
        {
          PyErr_SetString (PyExc_ValueError, "Path instance wrapping a NULL path");
          return -1;
        }
      if (transfer != GI_TRANSFER_NOTHING)
        {
          path = copy_cairo_path (path);
          if (path == NULL)
            return -1;
        }
      out->v_pointer = path;
      return 0;
    }

  if (is_cairo_info (iface, "FontOptions"))
    {
      cairo_font_options_t *options;
      cairo_font_options_t *(*copy_fn) (const cairo_font_options_t *);

      if (ensure_cairo_capi (capi) != 0)
        return -1;
      if (!PyObject_TypeCheck (value, capi->FontOptions_Type))
        return raise_expected_cairo_type ("FontOptions");
      options = ((PyGICairoFontOptions *)value)->font_options;
      if (options == NULL)
        {
          PyErr_SetString (PyExc_ValueError, "FontOptions instance wrapping a NULL font options");
          return -1;
        }
      if (transfer != GI_TRANSFER_NOTHING)
        {
          copy_fn = lookup_cairo_font_options_copy ();
          if (copy_fn == NULL)
            {
              PyErr_SetString (PyExc_RuntimeError, "cairo_font_options_copy unavailable");
              return -1;
            }
          options = copy_fn (options);
          if (options == NULL)
            {
              PyErr_SetString (PyExc_RuntimeError, "cairo_font_options_copy returned NULL");
              return -1;
            }
        }
      out->v_pointer = options;
      return 0;
    }

  if (is_cairo_info (iface, "Matrix"))
    {
      if (ensure_cairo_capi (capi) != 0)
        return -1;
      if (!PyObject_TypeCheck (value, capi->Matrix_Type))
        return raise_expected_cairo_type ("Matrix");
      out->v_pointer = &((PyGICairoMatrix *)value)->matrix;
      return 0;
    }

  if (is_cairo_namespace (iface))
    {
      PyErr_Format (PyExc_TypeError,
                    "Unsupported cairo foreign type %s",
                    gi_base_info_get_name (iface));
      return -1;
    }

  return 1;
}

PyObject *
pygi_foreign_cairo_to_py (GIBaseInfo *iface, gpointer pointer, GITransfer transfer)
{
  const PyGICairoCAPI *capi;

  if (pointer == NULL)
    Py_RETURN_NONE;

  capi = lookup_pycairo_capi ();
  if (ensure_cairo_capi (capi) != 0)
    return NULL;

  CAIRO_TO_PY_REFCOUNTED ("Context",
                          cairo_t *,
                          capi->Context_FromContext (value_ptr, capi->Context_Type, NULL),
                          lookup_cairo_reference,
                          "cairo_reference unavailable")
  CAIRO_TO_PY_REFCOUNTED ("Surface",
                          cairo_surface_t *,
                          capi->Surface_FromSurface (value_ptr, NULL),
                          lookup_cairo_surface_reference,
                          "cairo_surface_reference unavailable")
  CAIRO_TO_PY_REFCOUNTED ("FontFace",
                          cairo_font_face_t *,
                          capi->FontFace_FromFontFace (value_ptr),
                          lookup_cairo_font_face_reference,
                          "cairo_font_face_reference unavailable")
  CAIRO_TO_PY_REFCOUNTED ("ScaledFont",
                          cairo_scaled_font_t *,
                          capi->ScaledFont_FromScaledFont (value_ptr),
                          lookup_cairo_scaled_font_reference,
                          "cairo_scaled_font_reference unavailable")
  CAIRO_TO_PY_REFCOUNTED ("Pattern",
                          cairo_pattern_t *,
                          capi->Pattern_FromPattern (value_ptr, NULL),
                          lookup_cairo_pattern_reference,
                          "cairo_pattern_reference unavailable")
  CAIRO_TO_PY_REFCOUNTED ("Region",
                          cairo_region_t *,
                          capi->Region_FromRegion (value_ptr),
                          lookup_cairo_region_reference,
                          "cairo_region_reference unavailable")

  if (is_cairo_info (iface, "Path"))
    {
      return capi->Path_FromPath ((cairo_path_t *)pointer);
    }

  if (is_cairo_info (iface, "FontOptions"))
    {
      cairo_font_options_t *options = (cairo_font_options_t *)pointer;
      if (transfer == GI_TRANSFER_NOTHING)
        {
          cairo_font_options_t *(*copy_fn) (const cairo_font_options_t *)
              = lookup_cairo_font_options_copy ();
          if (copy_fn == NULL)
            {
              PyErr_SetString (PyExc_RuntimeError, "cairo_font_options_copy unavailable");
              return NULL;
            }
          options = copy_fn (options);
          if (options == NULL)
            {
              PyErr_SetString (PyExc_RuntimeError, "cairo_font_options_copy returned NULL");
              return NULL;
            }
        }
      return capi->FontOptions_FromFontOptions (options);
    }

  if (is_cairo_info (iface, "Matrix"))
    {
      return capi->Matrix_FromMatrix ((const cairo_matrix_t *)pointer);
    }

  return NULL;
}

int
pygi_foreign_cairo_boxed_from_py (PyObject *value, GIBaseInfo *iface, GValue *out)
{
  GIArgument arg = { 0 };
  int rc;

  rc = pygi_foreign_cairo_from_py (value, iface, GI_TRANSFER_NOTHING, &arg);
  if (rc != 0)
    return rc;

  g_value_set_boxed (out, arg.v_pointer);
  return 0;
}

#undef CAIRO_FROM_PY_REFCOUNTED
#undef CAIRO_TO_PY_REFCOUNTED
