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

#include "marshal/scalar.h"

#include <cairo.h>
#include <girepository/girepository.h>
#include <glib-object.h>
#include <stdbool.h>

static inline bool
gi_base_info_is_named (GIBaseInfo *info, const char *namespace_name, const char *name)
{
  return info != NULL && g_strcmp0 (gi_base_info_get_namespace (info), namespace_name) == 0
         && g_strcmp0 (gi_base_info_get_name (info), name) == 0;
}

static inline gsize
gi_struct_or_union_size (GIBaseInfo *info)
{
  if (gi_base_info_is_named (info, "cairo", "Matrix"))
    return sizeof (cairo_matrix_t);
  if (gi_base_info_is_named (info, "cairo", "Rectangle"))
    return sizeof (cairo_rectangle_t);
  if (gi_base_info_is_named (info, "cairo", "RectangleInt"))
    return sizeof (cairo_rectangle_int_t);
  if (gi_base_info_is_named (info, "cairo", "Glyph"))
    return sizeof (cairo_glyph_t);
  if (gi_base_info_is_named (info, "cairo", "TextCluster"))
    return sizeof (cairo_text_cluster_t);
  if (GI_IS_STRUCT_INFO (info))
    return gi_struct_info_get_size ((GIStructInfo *)info);
  if (GI_IS_UNION_INFO (info))
    return gi_union_info_get_size ((GIUnionInfo *)info);
  return 0;
}

static inline int
gi_struct_or_union_n_fields (GIBaseInfo *info)
{
  if (GI_IS_STRUCT_INFO (info))
    return gi_struct_info_get_n_fields ((GIStructInfo *)info);
  if (GI_IS_UNION_INFO (info))
    return gi_union_info_get_n_fields ((GIUnionInfo *)info);
  return 0;
}

static inline GIFieldInfo *
gi_struct_or_union_get_field (GIBaseInfo *info, guint index)
{
  if (GI_IS_STRUCT_INFO (info))
    return gi_struct_info_get_field ((GIStructInfo *)info, index);
  if (GI_IS_UNION_INFO (info))
    return gi_union_info_get_field ((GIUnionInfo *)info, index);
  return NULL;
}

static inline GITypeTag
gi_type_info_storage_tag (GITypeInfo *type_info)
{
  GITypeTag tag = gi_type_info_get_tag (type_info);
  if (tag == GI_TYPE_TAG_INTERFACE)
    {
      g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (type_info);
      if (iface != NULL && (GI_IS_ENUM_INFO (iface) || GI_IS_FLAGS_INFO (iface)))
        return gi_type_info_get_storage_type (type_info);
    }
  return tag;
}

static inline bool
gi_type_info_is_gvalue (GITypeInfo *type_info)
{
  if (type_info == NULL || gi_type_info_get_tag (type_info) != GI_TYPE_TAG_INTERFACE)
    return false;
  g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (type_info);
  return gi_base_info_is_named (iface, "GObject", "Value");
}

static inline bool
gi_type_info_is_variant (GITypeInfo *type_info)
{
  if (type_info == NULL || gi_type_info_get_tag (type_info) != GI_TYPE_TAG_INTERFACE)
    return false;
  g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (type_info);
  return gi_base_info_is_named (iface, "GLib", "Variant");
}

static inline bool
gi_type_info_is_param_spec (GITypeInfo *type_info)
{
  if (type_info == NULL || gi_type_info_get_tag (type_info) != GI_TYPE_TAG_INTERFACE)
    return false;
  g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (type_info);
  if (gi_base_info_is_named (iface, "GObject", "ParamSpec")
      || gi_base_info_is_named (iface, "GObject", "Param"))
    return true;
  if (iface != NULL && GI_IS_REGISTERED_TYPE_INFO (iface))
    {
      const char *type_name = gi_registered_type_info_get_type_name ((GIRegisteredTypeInfo *)iface);
      if (g_strcmp0 (type_name, "GParam") == 0)
        return true;
      GType gtype = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)iface);
      return gtype != G_TYPE_INVALID && gtype != G_TYPE_NONE && g_type_is_a (gtype, G_TYPE_PARAM);
    }
  return false;
}

static inline gsize
gi_type_info_element_size (GITypeInfo *type_info)
{
  switch (gi_type_info_storage_tag (type_info))
    {
#define PYGI_SCALAR PYGI_SCALAR_RETURN_SIZE

#include "marshal/scalar-tags.h"

#undef PYGI_SCALAR

    case GI_TYPE_TAG_UTF8:
    case GI_TYPE_TAG_FILENAME:
    case GI_TYPE_TAG_ARRAY:
    case GI_TYPE_TAG_INTERFACE:
    case GI_TYPE_TAG_GLIST:
    case GI_TYPE_TAG_GSLIST:
    case GI_TYPE_TAG_GHASH:
    case GI_TYPE_TAG_ERROR:
      return sizeof (gpointer);
    case GI_TYPE_TAG_VOID:
      return 0;
    }
  return 0;
}

static inline gsize
gi_type_info_array_element_size (GITypeInfo *type_info)
{
  if (gi_type_info_get_tag (type_info) == GI_TYPE_TAG_INTERFACE
      && !gi_type_info_is_gvalue (type_info) && !gi_type_info_is_pointer (type_info))
    {
      g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (type_info);
      if (iface != NULL && (GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface)))
        return gi_struct_or_union_size (iface);
    }
  return gi_type_info_element_size (type_info);
}

static inline int
gi_argument_get_length (GITypeInfo *type_info, GIArgument *arg, gsize *out)
{
  g_return_val_if_fail (type_info != NULL, -1);
  g_return_val_if_fail (arg != NULL, -1);
  g_return_val_if_fail (out != NULL, -1);

  switch (gi_type_info_get_tag (type_info))
    {
#define PYGI_SCALAR PYGI_SCALAR_GET_LENGTH

#include "marshal/scalar-tags.h"

#undef PYGI_SCALAR

    default:
      return -1;
    }
}

static inline int
gi_argument_set_length (GITypeInfo *type_info, gssize len, GIArgument *out)
{
  g_return_val_if_fail (type_info != NULL, -1);
  g_return_val_if_fail (out != NULL, -1);

  switch (gi_type_info_get_tag (type_info))
    {
#define PYGI_SCALAR PYGI_SCALAR_SET_LENGTH

#include "marshal/scalar-tags.h"

#undef PYGI_SCALAR

    default:
      return -1;
    }
}

static inline bool
gi_type_info_is_enum_or_flags (GITypeInfo *type_info)
{
  if (type_info == NULL || gi_type_info_get_tag (type_info) != GI_TYPE_TAG_INTERFACE)
    return false;
  g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (type_info);
  return iface != NULL && (GI_IS_ENUM_INFO (iface) || GI_IS_FLAGS_INFO (iface));
}

static inline void *
gi_argument_storage_pointer (GITypeTag tag, GIArgument *arg)
{
  switch (tag)
    {
#define PYGI_SCALAR PYGI_SCALAR_RETURN_GIARG_FIELD_POINTER

#include "marshal/scalar-tags.h"

#undef PYGI_SCALAR

    case GI_TYPE_TAG_UTF8:
    case GI_TYPE_TAG_FILENAME:
    case GI_TYPE_TAG_ARRAY:
    case GI_TYPE_TAG_INTERFACE:
    case GI_TYPE_TAG_GLIST:
    case GI_TYPE_TAG_GSLIST:
    case GI_TYPE_TAG_GHASH:
    case GI_TYPE_TAG_ERROR:
      return &arg->v_pointer;
    case GI_TYPE_TAG_VOID:
      return NULL;
    }
  return NULL;
}

int
pygi_load_array_element (GITypeInfo *elem_ti,
                         const char *base,
                         guint index,
                         gsize elem_size,
                         GIArgument *out);
