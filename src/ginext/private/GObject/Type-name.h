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

#ifndef GINEXT_UNIQUE_NAME_H
#define GINEXT_UNIQUE_NAME_H

#include "common.h"

/* Resolve `requested` to a GType name that's currently free in GLib's
 * registry. If `requested` itself is unused, returns a g_strdup of it.
 * Otherwise appends `_N` (N starts at 2) until a free slot is found.
 *
 * Returns a newly-allocated string the caller must free with g_free,
 * or NULL with a Python exception set if the namespace is exhausted. */
char *
unique_type_name (const char *requested);

#endif /* GINEXT_UNIQUE_NAME_H */
