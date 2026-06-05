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

/* list.c - GList/GSList argument marshalling. */
#include "GLib/List.h"

#include "GObject/Boxed.h"
#include "GObject/Object-info.h"
#include "marshal/container-element.h"

/**
 * list_element_can_use_pointer_slot:
 * @element: resolved container-element metadata
 *
 * Returns true for element kinds that this GList/GSList marshaller
 * stores directly in the gpointer data slot.
 */
static gboolean
list_element_can_use_pointer_slot (const PyGIContainerElement *element)
{
  if (!pygi_container_element_can_use_pointer_slot (element))
    return FALSE;

  switch (element->type.kind)
    {
    case PYGI_TYPE_INT32:
    case PYGI_TYPE_UINT32:
    case PYGI_TYPE_UTF8:
    case PYGI_TYPE_FILENAME:
    case PYGI_TYPE_GTYPE:
      return TRUE;
    default:
      return FALSE;
    }
}

/**
 * list_element_is_opaque:
 * @elem_ti: list element GI metadata, or %NULL
 *
 * Returns true for element shapes this marshaller intentionally treats
 * as opaque G[S]List pointers rather than Python sequences.
 */
static gboolean
list_element_is_opaque (GITypeInfo *elem_ti)
{
  if (elem_ti == NULL)
    return TRUE;

  PyGIType type = { 0 };
  if (pygi_type_from_gi (elem_ti, &type) != 0)
    return FALSE;

  switch (type.kind)
    {
    case PYGI_TYPE_VOID:
    case PYGI_TYPE_BOOLEAN:
    case PYGI_TYPE_INT8:
    case PYGI_TYPE_UINT8:
    case PYGI_TYPE_INT16:
    case PYGI_TYPE_UINT16:
    case PYGI_TYPE_GLIST:
    case PYGI_TYPE_GSLIST:
      return TRUE;
    default:
      return FALSE;
    }
}

static int
list_item_from_py (PyObject *item, GITypeInfo *elem_ti, GITransfer transfer, gpointer *out_data)
{
  PyGIContainerElement element;
  if (pygi_container_element_init (&element, elem_ti) == 0
      && list_element_can_use_pointer_slot (&element))
    return pygi_container_element_pointer_from_py (&element, item, transfer, out_data);

  GITypeTag elem_tag = gi_type_info_get_tag (elem_ti);
  switch (elem_tag)
    {
    case GI_TYPE_TAG_INTERFACE:
      {
        g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (elem_ti);
        if (iface == NULL)
          {
            PyErr_SetString (PyExc_NotImplementedError,
                             "GList/GSList element interface metadata missing");
            return -1;
          }
        if (item == Py_None)
          {
            *out_data = NULL;
            return 0;
          }
        if (GI_IS_OBJECT_INFO (iface) || GI_IS_INTERFACE_INFO (iface))
          {
            GIArgument tmp = { 0 };
            if (pygi_object_info_from_py (item, &tmp) != 0)
              return -1;
            *out_data = tmp.v_pointer;
            return 0;
          }
        if (GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface))
          {
            if (pygi_boxed_get (item, out_data) != 0)
              return -1;
            return 0;
          }
        PyErr_SetString (PyExc_NotImplementedError,
                         "GList/GSList element interface kind not supported");
        return -1;
      }
    default:
      PyErr_SetString (PyExc_NotImplementedError,
                       "GList/GSList argument element type is not supported");
      return -1;
    }
}

static void
free_list_items_if_needed (gpointer list, gboolean singly_linked, GITypeInfo *elem_ti)
{
  GITypeTag elem_tag = gi_type_info_get_tag (elem_ti);
  gboolean free_items = elem_tag == GI_TYPE_TAG_UTF8 || elem_tag == GI_TYPE_TAG_FILENAME;
  if (singly_linked)
    {
      if (free_items)
        g_slist_free_full ((GSList *)list, g_free);
      else
        g_slist_free ((GSList *)list);
    }
  else
    {
      if (free_items)
        g_list_free_full ((GList *)list, g_free);
      else
        g_list_free ((GList *)list);
    }
}

static int
list_from_py (PyObject *value,
              GITypeInfo *ti,
              GITransfer transfer,
              GIArgument *dest,
              PyGIArgCleanup *cleanup,
              gboolean singly_linked)
{
  g_return_val_if_fail (ti != NULL, -1);
  g_return_val_if_fail (GI_IS_TYPE_INFO (ti), -1);
  g_return_val_if_fail (dest != NULL, -1);
  g_return_val_if_fail (cleanup != NULL, -1);

  if (value == Py_None)
    {
      dest->v_pointer = NULL;
      return 0;
    }

  g_autoptr (GITypeInfo) elem_ti = gi_type_info_get_param_type (ti, 0);
  if (list_element_is_opaque (elem_ti))
    {
      /* Opaque G[S]List<gpointer>: accept a boxed wrapper or fail. */
      gpointer boxed_ptr = NULL;
      if (pygi_boxed_get (value, &boxed_ptr) == 0)
        {
          dest->v_pointer = boxed_ptr;
          return 0;
        }
      PyErr_Clear ();
      PyErr_SetString (PyExc_TypeError,
                       singly_linked ? "GSList argument with no element-type metadata "
                                       "accepts only None or a GLib.SList instance"
                                     : "GList argument with no element-type metadata "
                                       "accepts only None or a GLib.List instance");
      return -1;
    }

  PyObject *seq = PySequence_Fast (value,
                                   singly_linked ? "expected a sequence for GSList"
                                                 : "expected a sequence for GList");
  if (seq == NULL)
    return -1;

  gpointer list = NULL;
  Py_ssize_t n = PySequence_Fast_GET_SIZE (seq);
  for (Py_ssize_t i = 0; i < n; i++)
    {
      gpointer data = NULL;
      PyObject *item = PySequence_Fast_GET_ITEM (seq, i);
      if (list_item_from_py (item, elem_ti, transfer, &data) != 0)
        {
          Py_DECREF (seq);
          if (transfer == GI_TRANSFER_EVERYTHING)
            free_list_items_if_needed (list, singly_linked, elem_ti);
          else if (singly_linked)
            g_slist_free ((GSList *)list);
          else
            g_list_free ((GList *)list);
          return -1;
        }
      list = singly_linked ? (gpointer)g_slist_append ((GSList *)list, data)
                           : (gpointer)g_list_append ((GList *)list, data);
    }

  Py_DECREF (seq);
  dest->v_pointer = list;
  if (transfer == GI_TRANSFER_NOTHING && list != NULL)
    {
      cleanup->kind = singly_linked ? PYGI_ARG_CLEANUP_GSLIST : PYGI_ARG_CLEANUP_GLIST;
      cleanup->ptr = list;
    }
  return 0;
}

int
pygi_glist_from_py (PyObject *value,
                    GITypeInfo *ti,
                    GITransfer transfer,
                    GIArgument *dest,
                    PyGIArgCleanup *cleanup)
{
  return list_from_py (value, ti, transfer, dest, cleanup, FALSE);
}

int
pygi_slist_from_py (PyObject *value,
                    GITypeInfo *ti,
                    GITransfer transfer,
                    GIArgument *dest,
                    PyGIArgCleanup *cleanup)
{
  return list_from_py (value, ti, transfer, dest, cleanup, TRUE);
}
