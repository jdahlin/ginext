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

#include <stdbool.h>
#include <stddef.h>

typedef void *PyGIJittedTrampoline;

typedef enum
{
  PYGI_TY_VOID = 0,
  PYGI_TY_BOOL,
  PYGI_TY_INT8,
  PYGI_TY_UINT8,
  PYGI_TY_INT16,
  PYGI_TY_UINT16,
  PYGI_TY_INT32,
  PYGI_TY_UINT32,
  PYGI_TY_INT64,
  PYGI_TY_UINT64,
  PYGI_TY_UNICHAR,
  PYGI_TY_FLOAT,
  PYGI_TY_DOUBLE,
  PYGI_TY_UTF8,
  PYGI_TY_GOBJECT,
} PyGIJitTypeKind;

#define PYGI_MAX_ARGS 32

typedef struct
{
  PyGIJitTypeKind ret;
  PyGIJitTypeKind args[PYGI_MAX_ARGS];
  int nargs;
  bool has_self;
} PyGISignature;
