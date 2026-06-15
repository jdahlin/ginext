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

#include "GIRepository/BaseInfo.h"
#include "marshal/scalar.h"
#include "runtime/type-info.h"

#include <girepository/girepository.h>

GIRepository *
pygi_shared_repository (void)
{
  static GIRepository *default_repo = NULL;
  if (default_repo == NULL)
    default_repo = gi_repository_dup_default ();
  return default_repo;
}

int
pygi_load_array_element (GITypeInfo *elem_ti,
                         const char *base,
                         guint index,
                         gsize elem_size,
                         GIArgument *out)
{
  const char *ptr = base + ((size_t)index * elem_size);
  GITypeTag storage_tag = gi_type_info_storage_tag (elem_ti);
  switch (storage_tag)
    {
#define PYGI_SCALAR PYGI_SCALAR_LOAD_OUT_FROM_PTR

#include "marshal/scalar-tags.h"

#undef PYGI_SCALAR

    default:
      if (gi_type_info_get_tag (elem_ti) == GI_TYPE_TAG_UTF8
          || gi_type_info_get_tag (elem_ti) == GI_TYPE_TAG_FILENAME)
        {
          out->v_string = *(char *const *)ptr;
          return 0;
        }
      if (gi_type_info_get_tag (elem_ti) == GI_TYPE_TAG_ARRAY)
        {
          out->v_pointer = *(void *const *)ptr;
          return 0;
        }
      if (gi_type_info_get_tag (elem_ti) == GI_TYPE_TAG_INTERFACE)
        {
          g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (elem_ti);
          if (iface != NULL && (GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface))
              && !gi_type_info_is_pointer (elem_ti))
            out->v_pointer = (void *)ptr;
          else
            out->v_pointer = *(void *const *)ptr;
          return 0;
        }
      return -1;
    }
}
