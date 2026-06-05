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

#pragma once

#include <cairo.h>
#include <dlfcn.h>
#include <string.h>

typedef struct
{
  PyObject_HEAD cairo_t *ctx;
  PyObject *base;
} PyGICairoContext;

typedef struct
{
  PyObject_HEAD cairo_font_face_t *font_face;
} PyGICairoFontFace;

typedef struct
{
  PyObject_HEAD cairo_font_options_t *font_options;
} PyGICairoFontOptions;

typedef struct
{
  PyObject_HEAD cairo_matrix_t matrix;
} PyGICairoMatrix;

typedef struct
{
  PyObject_HEAD cairo_path_t *path;
} PyGICairoPath;

typedef struct
{
  PyObject_HEAD cairo_pattern_t *pattern;
  PyObject *base;
} PyGICairoPattern;

typedef struct
{
  PyObject_HEAD cairo_region_t *region;
} PyGICairoRegion;

typedef struct
{
  PyObject_HEAD cairo_scaled_font_t *scaled_font;
} PyGICairoScaledFont;

typedef struct
{
  PyObject_HEAD cairo_surface_t *surface;
  PyObject *base;
} PyGICairoSurface;

typedef struct
{
  PyTypeObject *Context_Type;
  PyObject *(*Context_FromContext) (cairo_t *ctx, PyTypeObject *type, PyObject *base);
  PyTypeObject *FontFace_Type;
  PyTypeObject *ToyFontFace_Type;
  PyObject *(*FontFace_FromFontFace) (cairo_font_face_t *font_face);
  PyTypeObject *FontOptions_Type;
  PyObject *(*FontOptions_FromFontOptions) (cairo_font_options_t *font_options);
  PyTypeObject *Matrix_Type;
  PyObject *(*Matrix_FromMatrix) (const cairo_matrix_t *matrix);
  PyTypeObject *Path_Type;
  PyObject *(*Path_FromPath) (cairo_path_t *path);
  PyTypeObject *Pattern_Type;
  PyTypeObject *SolidPattern_Type;
  PyTypeObject *SurfacePattern_Type;
  PyTypeObject *Gradient_Type;
  PyTypeObject *LinearGradient_Type;
  PyTypeObject *RadialGradient_Type;
  PyObject *(*Pattern_FromPattern) (cairo_pattern_t *pattern, PyObject *base);
  PyTypeObject *ScaledFont_Type;
  PyObject *(*ScaledFont_FromScaledFont) (cairo_scaled_font_t *scaled_font);
  PyTypeObject *Surface_Type;
  PyTypeObject *ImageSurface_Type;
  PyTypeObject *PDFSurface_Type;
  PyTypeObject *PSSurface_Type;
  PyTypeObject *SVGSurface_Type;
  PyTypeObject *Win32Surface_Type;
  PyTypeObject *Win32PrintingSurface_Type;
  PyTypeObject *XCBSurface_Type;
  PyTypeObject *XlibSurface_Type;
  PyObject *(*Surface_FromSurface) (cairo_surface_t *surface, PyObject *base);
  int (*Check_Status) (cairo_status_t status);
  PyTypeObject *RectangleInt_Type;
  PyObject *(*RectangleInt_FromRectangleInt) (const cairo_rectangle_int_t *rectangle_int);
  PyTypeObject *Region_Type;
  PyObject *(*Region_FromRegion) (cairo_region_t *region);
  PyTypeObject *RecordingSurface_Type;
} PyGICairoCAPI;

static inline const PyGICairoCAPI *
lookup_pycairo_capi (void)
{
  static const PyGICairoCAPI *capi = NULL;
  static int tried = 0;

  if (tried)
    return capi;

  tried = 1;
  capi = (const PyGICairoCAPI *)PyCapsule_Import ("cairo.CAPI", 0);
  if (capi == NULL)
    PyErr_Clear ();
  return capi;
}

static inline int
is_cairo_info (GIBaseInfo *iface, const char *name)
{
  const char *namespace_name;
  const char *type_name;

  if (iface == NULL)
    return 0;

  namespace_name = gi_base_info_get_namespace (iface);
  type_name = gi_base_info_get_name (iface);
  return namespace_name != NULL && type_name != NULL && strcmp (namespace_name, "cairo") == 0
         && strcmp (type_name, name) == 0;
}

static inline int
is_cairo_namespace (GIBaseInfo *iface)
{
  const char *namespace_name;

  if (iface == NULL)
    return 0;
  namespace_name = gi_base_info_get_namespace (iface);
  return namespace_name != NULL && strcmp (namespace_name, "cairo") == 0;
}

static inline int
raise_expected_cairo_type (const char *type_name)
{
  PyErr_Format (PyExc_TypeError, "Expected cairo.%s", type_name);
  return -1;
}

#define DEFINE_DLSYM_LOOKUP(func_name, ret_type, arg_type, symbol_name)                          \
  static inline ret_type (*func_name (void)) (arg_type)                                          \
  {                                                                                              \
    static ret_type (*func) (arg_type) = NULL;                                                   \
    static int looked_up = 0;                                                                    \
                                                                                                 \
    if (!looked_up)                                                                              \
      {                                                                                          \
        func = (ret_type(*)(arg_type))dlsym (RTLD_DEFAULT, symbol_name);                         \
        looked_up = 1;                                                                           \
      }                                                                                          \
    return func;                                                                                 \
  }

DEFINE_DLSYM_LOOKUP (lookup_cairo_reference, cairo_t *, cairo_t *, "cairo_reference")
DEFINE_DLSYM_LOOKUP (lookup_cairo_surface_reference,
                     cairo_surface_t *,
                     cairo_surface_t *,
                     "cairo_surface_reference")
DEFINE_DLSYM_LOOKUP (lookup_cairo_font_face_reference,
                     cairo_font_face_t *,
                     cairo_font_face_t *,
                     "cairo_font_face_reference")
DEFINE_DLSYM_LOOKUP (lookup_cairo_scaled_font_reference,
                     cairo_scaled_font_t *,
                     cairo_scaled_font_t *,
                     "cairo_scaled_font_reference")
DEFINE_DLSYM_LOOKUP (lookup_cairo_pattern_reference,
                     cairo_pattern_t *,
                     cairo_pattern_t *,
                     "cairo_pattern_reference")
DEFINE_DLSYM_LOOKUP (lookup_cairo_region_reference,
                     cairo_region_t *,
                     cairo_region_t *,
                     "cairo_region_reference")
DEFINE_DLSYM_LOOKUP (lookup_cairo_font_options_copy,
                     cairo_font_options_t *,
                     const cairo_font_options_t *,
                     "cairo_font_options_copy")

#undef DEFINE_DLSYM_LOOKUP

static inline int
ensure_cairo_capi (const PyGICairoCAPI *capi)
{
  if (capi != NULL)
    return 0;
  PyErr_SetString (PyExc_ImportError, "cairo foreign support unavailable");
  return -1;
}

#define CAIRO_FROM_PY_REFCOUNTED(info_name, py_type_field, wrapper_type, field_name, ptr_type,   \
                                 expected_name, lookup_ref, missing_ref_msg)                     \
  if (is_cairo_info (iface, info_name))                                                          \
    {                                                                                            \
      ptr_type value_ptr;                                                                        \
      ptr_type (*reference_fn) (ptr_type);                                                       \
                                                                                                 \
      if (ensure_cairo_capi (capi) != 0)                                                        \
        return -1;                                                                               \
      if (!PyObject_TypeCheck (value, capi->py_type_field))                                      \
        return raise_expected_cairo_type (expected_name);                                        \
      value_ptr = ((wrapper_type *)value)->field_name;                                           \
      if (value_ptr == NULL)                                                                     \
        {                                                                                        \
          PyErr_Format (PyExc_ValueError, "%s instance wrapping a NULL value", expected_name);   \
          return -1;                                                                             \
        }                                                                                        \
      if (transfer != GI_TRANSFER_NOTHING)                                                       \
        {                                                                                        \
          reference_fn = lookup_ref ();                                                          \
          if (reference_fn == NULL)                                                              \
            {                                                                                    \
              PyErr_SetString (PyExc_RuntimeError, missing_ref_msg);                             \
              return -1;                                                                         \
            }                                                                                    \
          value_ptr = reference_fn (value_ptr);                                                  \
        }                                                                                        \
      out->v_pointer = value_ptr;                                                                \
      return 0;                                                                                  \
    }

#define CAIRO_TO_PY_REFCOUNTED(info_name, ptr_type, from_expr, lookup_ref, missing_ref_msg)      \
  if (is_cairo_info (iface, info_name))                                                          \
    {                                                                                            \
      ptr_type value_ptr = (ptr_type)pointer;                                                    \
      ptr_type (*reference_fn) (ptr_type);                                                       \
                                                                                                 \
      if (transfer == GI_TRANSFER_NOTHING)                                                       \
        {                                                                                        \
          reference_fn = lookup_ref ();                                                          \
          if (reference_fn == NULL)                                                              \
            {                                                                                    \
              PyErr_SetString (PyExc_RuntimeError, missing_ref_msg);                             \
              return NULL;                                                                       \
            }                                                                                    \
          value_ptr = reference_fn (value_ptr);                                                  \
        }                                                                                        \
      return (from_expr);                                                                        \
    }

static inline cairo_path_t *
copy_cairo_path (cairo_path_t *path)
{
  cairo_surface_t *(*surface_create) (cairo_format_t, int, int);
  cairo_t *(*context_create) (cairo_surface_t *);
  cairo_status_t (*append_path) (cairo_t *, const cairo_path_t *);
  cairo_path_t *(*copy_path) (cairo_t *);
  void (*context_destroy) (cairo_t *);
  void (*surface_destroy) (cairo_surface_t *);
  cairo_surface_t *surface;
  cairo_t *context;
  cairo_path_t *copy;

  surface_create = (cairo_surface_t * (*)(cairo_format_t, int, int))dlsym (RTLD_DEFAULT,
                                                                            "cairo_image_surface_create");
  context_create = (cairo_t * (*)(cairo_surface_t *))dlsym (RTLD_DEFAULT, "cairo_create");
  append_path = (cairo_status_t (*)(cairo_t *, const cairo_path_t *))dlsym (RTLD_DEFAULT,
                                                                             "cairo_append_path");
  copy_path = (cairo_path_t * (*)(cairo_t *))dlsym (RTLD_DEFAULT, "cairo_copy_path");
  context_destroy = (void (*)(cairo_t *))dlsym (RTLD_DEFAULT, "cairo_destroy");
  surface_destroy = (void (*)(cairo_surface_t *))dlsym (RTLD_DEFAULT, "cairo_surface_destroy");

  if (surface_create == NULL || context_create == NULL || append_path == NULL || copy_path == NULL
      || context_destroy == NULL || surface_destroy == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "cairo path copy helpers unavailable");
      return NULL;
    }

  surface = surface_create (CAIRO_FORMAT_ARGB32, 0, 0);
  if (surface == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "cairo_image_surface_create returned NULL");
      return NULL;
    }
  context = context_create (surface);
  if (context == NULL)
    {
      surface_destroy (surface);
      PyErr_SetString (PyExc_RuntimeError, "cairo_create returned NULL");
      return NULL;
    }
  append_path (context, path);
  copy = copy_path (context);
  context_destroy (context);
  surface_destroy (surface);
  if (copy == NULL)
    PyErr_SetString (PyExc_RuntimeError, "cairo_copy_path returned NULL");
  return copy;
}
