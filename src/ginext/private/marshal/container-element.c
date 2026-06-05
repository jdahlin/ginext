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

#include "marshal/container-element.h"

static gboolean
container_element_is_int_kind (PyGITypeKind kind)
{
  switch (kind)
    {
    case PYGI_TYPE_INT8:
    case PYGI_TYPE_INT16:
    case PYGI_TYPE_INT32:
    case PYGI_TYPE_INT64:
    case PYGI_TYPE_UINT8:
    case PYGI_TYPE_UINT16:
    case PYGI_TYPE_UINT32:
    case PYGI_TYPE_UINT64:
      return TRUE;
    default:
      return FALSE;
    }
}

typedef enum
{
  CONTAINER_POINTER_SLOT,
  CONTAINER_HASH_POINTER,
} ContainerPointerStorage;

static int
container_element_init_enum_or_flags (PyGIContainerElement *element, GITypeInfo *ti)
{
  g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (ti);
  if (iface == NULL || (!GI_IS_ENUM_INFO (iface) && !GI_IS_FLAGS_INFO (iface)))
    return 0;

  element->type = (PyGIType){
    .kind = PYGI_TYPE_INT32,
    .gi_tag = GI_TYPE_TAG_INT32,
    .transfer = GI_TRANSFER_NOTHING,
    .gtype = G_TYPE_INVALID,
    .is_pointer = FALSE,
  };
  element->is_string = FALSE;
  element->is_direct = TRUE;
  return 1;
}

int
pygi_container_element_init (PyGIContainerElement *element, GITypeInfo *ti)
{
  g_return_val_if_fail (element != NULL, -1);
  g_return_val_if_fail (ti != NULL, -1);

  *element = (PyGIContainerElement){ 0 };
  if (gi_type_info_get_tag (ti) == GI_TYPE_TAG_INTERFACE)
    {
      int rc = container_element_init_enum_or_flags (element, ti);
      if (rc != 0)
        return rc < 0 ? -1 : 0;
    }

  if (pygi_type_from_gi (ti, &element->type) != 0)
    return -1;

  element->is_string
      = element->type.kind == PYGI_TYPE_UTF8 || element->type.kind == PYGI_TYPE_FILENAME;
  element->is_direct = pygi_type_is_direct_storage (&element->type);
  return element->is_direct ? 0 : -1;
}

gboolean
pygi_container_element_can_use_pointer_slot (const PyGIContainerElement *element)
{
  if (element == NULL || !element->is_direct)
    return FALSE;
  return element->is_string || container_element_is_int_kind (element->type.kind)
         || element->type.kind == PYGI_TYPE_GTYPE;
}

int
pygi_container_element_argument_from_py (const PyGIContainerElement *element,
                                         PyObject *py,
                                         GIArgument *out)
{
  g_return_val_if_fail (element != NULL, -1);
  g_return_val_if_fail (out != NULL, -1);
  PyGIValue value = pygi_value_for_giarg (&element->type, out);
  return pygi_value_from_py (py, &value);
}

static gpointer
container_element_box_wide_hash_pointer (const PyGIContainerElement *element, const GIArgument *arg)
{
  switch (element->type.kind)
    {
    case PYGI_TYPE_DOUBLE:
      {
        double *p = g_new (double, 1);
        *p = arg->v_double;
        return p;
      }
    case PYGI_TYPE_FLOAT:
      {
        float *p = g_new (float, 1);
        *p = arg->v_float;
        return p;
      }
    case PYGI_TYPE_INT64:
      {
        gint64 *p = g_new (gint64, 1);
        *p = arg->v_int64;
        return p;
      }
    case PYGI_TYPE_UINT64:
      {
        guint64 *p = g_new (guint64, 1);
        *p = arg->v_uint64;
        return p;
      }
    default:
      return NULL;
    }
}

static int
container_element_pointer_from_argument (const PyGIContainerElement *element,
                                         const GIArgument *arg,
                                         GITransfer transfer,
                                         ContainerPointerStorage storage,
                                         gpointer *out)
{
  g_return_val_if_fail (element != NULL, -1);
  g_return_val_if_fail (arg != NULL, -1);
  g_return_val_if_fail (out != NULL, -1);

  if (storage == CONTAINER_HASH_POINTER)
    {
      gpointer wide = container_element_box_wide_hash_pointer (element, arg);
      if (wide != NULL)
        {
          *out = wide;
          return 0;
        }
    }

  if (element->is_string)
    {
      if (transfer == GI_TRANSFER_EVERYTHING && arg->v_string != NULL)
        {
          *out = g_strdup (arg->v_string);
          if (*out == NULL)
            {
              PyErr_NoMemory ();
              return -1;
            }
          return 0;
        }
      *out = arg->v_string;
      return 0;
    }

  switch (element->type.kind)
    {
    case PYGI_TYPE_POINTER:
      if (storage == CONTAINER_HASH_POINTER)
        {
          *out = arg->v_pointer;
          return 0;
        }
      break;
    case PYGI_TYPE_BOOLEAN:
      if (storage == CONTAINER_HASH_POINTER)
        {
          *out = GINT_TO_POINTER (arg->v_boolean);
          return 0;
        }
      break;
    case PYGI_TYPE_INT8:
      *out = GINT_TO_POINTER ((gint)arg->v_int8);
      return 0;
    case PYGI_TYPE_UINT8:
      *out = GUINT_TO_POINTER ((guint)arg->v_uint8);
      return 0;
    case PYGI_TYPE_INT16:
      *out = GINT_TO_POINTER ((gint)arg->v_int16);
      return 0;
    case PYGI_TYPE_UINT16:
      *out = GUINT_TO_POINTER ((guint)arg->v_uint16);
      return 0;
    case PYGI_TYPE_INT32:
      *out = GINT_TO_POINTER (arg->v_int32);
      return 0;
    case PYGI_TYPE_UINT32:
      *out = GUINT_TO_POINTER (arg->v_uint32);
      return 0;
    case PYGI_TYPE_UNICHAR:
      if (storage == CONTAINER_HASH_POINTER)
        {
          *out = GUINT_TO_POINTER (arg->v_uint32);
          return 0;
        }
      break;
    case PYGI_TYPE_INT64:
      *out = GINT_TO_POINTER ((gint)arg->v_int64);
      return 0;
    case PYGI_TYPE_UINT64:
      *out = GUINT_TO_POINTER ((guint)arg->v_uint64);
      return 0;
    case PYGI_TYPE_GTYPE:
      *out = GSIZE_TO_POINTER ((gsize)arg->v_size);
      return 0;
    default:
      break;
    }

  PyErr_SetString (PyExc_NotImplementedError,
                   storage == CONTAINER_HASH_POINTER
                       ? "container hash element type not supported"
                       : "container pointer element type not supported");
  return -1;
}

int
pygi_container_element_pointer_from_py (const PyGIContainerElement *element,
                                        PyObject *py,
                                        GITransfer transfer,
                                        gpointer *out)
{
  g_return_val_if_fail (element != NULL, -1);
  g_return_val_if_fail (out != NULL, -1);
  GIArgument arg = { 0 };
  if (pygi_container_element_argument_from_py (element, py, &arg) != 0)
    return -1;
  return container_element_pointer_from_argument (element,
                                                  &arg,
                                                  transfer,
                                                  CONTAINER_POINTER_SLOT,
                                                  out);
}

PyObject *
pygi_container_element_pointer_to_py (const PyGIContainerElement *element, gpointer ptr)
{
  g_return_val_if_fail (element != NULL, NULL);
  GIArgument arg = { .v_pointer = ptr };
  PyGIValue value = pygi_value_for_giarg (&element->type, &arg);
  return pygi_value_to_py (&value);
}

gboolean
pygi_container_element_can_use_hash_pointer (const PyGIContainerElement *element)
{
  return element != NULL && element->is_direct;
}

int
pygi_container_element_hash_pointer_from_argument (const PyGIContainerElement *element,
                                                   const GIArgument *arg,
                                                   GITransfer transfer,
                                                   gpointer *out)
{
  return container_element_pointer_from_argument (element,
                                                  arg,
                                                  transfer,
                                                  CONTAINER_HASH_POINTER,
                                                  out);
}

PyObject *
pygi_container_element_hash_pointer_to_py (const PyGIContainerElement *element, gpointer ptr)
{
  g_return_val_if_fail (element != NULL, NULL);

  GIArgument arg = { 0 };
  switch (element->type.kind)
    {
    case PYGI_TYPE_DOUBLE:
      arg.v_double = ptr ? *(double *)ptr : 0.0;
      break;
    case PYGI_TYPE_FLOAT:
      arg.v_float = ptr ? *(float *)ptr : 0.0f;
      break;
    case PYGI_TYPE_INT64:
      arg.v_int64 = ptr ? *(gint64 *)ptr : 0;
      break;
    case PYGI_TYPE_UINT64:
      arg.v_uint64 = ptr ? *(guint64 *)ptr : 0;
      break;
    case PYGI_TYPE_POINTER:
    case PYGI_TYPE_UTF8:
    case PYGI_TYPE_FILENAME:
      arg.v_pointer = ptr;
      break;
    case PYGI_TYPE_BOOLEAN:
      arg.v_boolean = GPOINTER_TO_INT (ptr);
      break;
    case PYGI_TYPE_INT8:
      arg.v_int8 = (gint8)GPOINTER_TO_INT (ptr);
      break;
    case PYGI_TYPE_UINT8:
      arg.v_uint8 = (guint8)GPOINTER_TO_UINT (ptr);
      break;
    case PYGI_TYPE_INT16:
      arg.v_int16 = (gint16)GPOINTER_TO_INT (ptr);
      break;
    case PYGI_TYPE_UINT16:
      arg.v_uint16 = (guint16)GPOINTER_TO_UINT (ptr);
      break;
    case PYGI_TYPE_INT32:
      arg.v_int32 = GPOINTER_TO_INT (ptr);
      break;
    case PYGI_TYPE_UINT32:
    case PYGI_TYPE_UNICHAR:
      arg.v_uint32 = GPOINTER_TO_UINT (ptr);
      break;
    case PYGI_TYPE_GTYPE:
      arg.v_size = (gsize)GPOINTER_TO_SIZE (ptr);
      break;
    default:
      PyErr_SetString (PyExc_NotImplementedError, "container hash element type not supported");
      return NULL;
    }

  PyGIValue value = pygi_value_for_giarg (&element->type, &arg);
  return pygi_value_to_py (&value);
}

gsize
pygi_container_element_inline_size (const PyGIContainerElement *element)
{
  if (element == NULL || !element->is_direct)
    return 0;

  return pygi_type_storage_size (&element->type);
}

int
pygi_container_element_inline_from_py (const PyGIContainerElement *element,
                                       PyObject *py,
                                       GITransfer transfer,
                                       void *dst)
{
  g_return_val_if_fail (element != NULL, -1);
  g_return_val_if_fail (dst != NULL, -1);

  if (element->is_string)
    {
      GIArgument arg = { 0 };
      PyGIValue value = pygi_value_for_giarg (&element->type, &arg);
      if (pygi_value_from_py (py, &value) != 0)
        return -1;
      char *s = NULL;
      if (transfer == GI_TRANSFER_EVERYTHING && arg.v_string != NULL)
        {
          s = g_strdup (arg.v_string);
          if (s == NULL)
            {
              PyErr_NoMemory ();
              return -1;
            }
        }
      else
        {
          s = arg.v_string;
        }
      *(char **)dst = s;
      return 0;
    }

  PyGIValue value = pygi_value_for_memory (&element->type, dst);
  return pygi_value_from_py (py, &value);
}

PyObject *
pygi_container_element_inline_to_py (const PyGIContainerElement *element, const void *src)
{
  g_return_val_if_fail (element != NULL, NULL);
  g_return_val_if_fail (src != NULL, NULL);
  PyGIValue value = pygi_value_for_memory (&element->type, (void *)src);
  return pygi_value_to_py (&value);
}
