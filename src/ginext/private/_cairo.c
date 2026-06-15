/* Copyright 2026 Johan Dahlin
 *
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */

#include <Python.h>
#include <cairo-gobject.h>

static PyObject *
py_ensure_gobject_types (PyObject *m, PyObject *args)
{
  (void)m;
  if (!PyArg_ParseTuple (args, ""))
    return NULL;

  (void)cairo_gobject_context_get_type ();
  (void)cairo_gobject_device_get_type ();
  (void)cairo_gobject_matrix_get_type ();
  (void)cairo_gobject_pattern_get_type ();
  (void)cairo_gobject_surface_get_type ();
  (void)cairo_gobject_rectangle_get_type ();
  (void)cairo_gobject_scaled_font_get_type ();
  (void)cairo_gobject_font_face_get_type ();
  (void)cairo_gobject_font_options_get_type ();
  (void)cairo_gobject_rectangle_int_get_type ();
  (void)cairo_gobject_region_get_type ();
  (void)cairo_gobject_glyph_get_type ();
  (void)cairo_gobject_text_cluster_get_type ();
  (void)cairo_gobject_status_get_type ();
  (void)cairo_gobject_content_get_type ();
  (void)cairo_gobject_operator_get_type ();
  (void)cairo_gobject_antialias_get_type ();
  (void)cairo_gobject_fill_rule_get_type ();
  (void)cairo_gobject_line_cap_get_type ();
  (void)cairo_gobject_line_join_get_type ();
  (void)cairo_gobject_text_cluster_flags_get_type ();
  (void)cairo_gobject_font_slant_get_type ();
  (void)cairo_gobject_font_weight_get_type ();
  (void)cairo_gobject_subpixel_order_get_type ();
  (void)cairo_gobject_hint_style_get_type ();
  (void)cairo_gobject_hint_metrics_get_type ();
  (void)cairo_gobject_font_type_get_type ();
  (void)cairo_gobject_path_data_type_get_type ();
  (void)cairo_gobject_device_type_get_type ();
  (void)cairo_gobject_surface_type_get_type ();
  (void)cairo_gobject_format_get_type ();
  (void)cairo_gobject_pattern_type_get_type ();
  (void)cairo_gobject_extend_get_type ();
  (void)cairo_gobject_filter_get_type ();
  (void)cairo_gobject_region_overlap_get_type ();

  Py_RETURN_NONE;
}

static PyMethodDef methods[] = {
  { "ensure_gobject_types", py_ensure_gobject_types, METH_VARARGS, NULL },
  { NULL }
};

static struct PyModuleDef moddef = {
  PyModuleDef_HEAD_INIT, .m_name = "_cairo", .m_size = -1, .m_methods = methods,
};

PyMODINIT_FUNC
PyInit__cairo (void)
{
  PyObject *m = PyModule_Create (&moddef);
  if (!m)
    return NULL;

#ifdef Py_GIL_DISABLED
  PyUnstable_Module_SetGIL (m, Py_MOD_GIL_NOT_USED);
#endif

  return m;
}
