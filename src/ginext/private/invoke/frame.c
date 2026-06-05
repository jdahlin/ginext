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

/* invoke/frame.c - per-call invocation frame cleanup. */
#include "invoke/frame.h"

#include <girepository/girepository.h>

PyObject *
pygi_invoke_frame_fail (PyGIInvokeFrame *frame)
{
  pygi_arg_cleanups_clear (frame->cleanups, frame->n_gi_args);
  for (size_t j = 0; j < frame->out_tis_count; j++)
    {
      if (frame->out_tis[j] != NULL)
        gi_base_info_unref ((GIBaseInfo *)frame->out_tis[j]);
    }
  for (size_t k = 0; k < frame->n_gi_args; k++)
    {
      if (frame->in_len_ti[k] != NULL)
        gi_base_info_unref ((GIBaseInfo *)frame->in_len_ti[k]);
    }
  return NULL;
}

void
pygi_invoke_frame_clear (PyGIInvokeFrame *frame)
{
  for (size_t j = 0; j < frame->out_tis_count; j++)
    {
      if (frame->out_tis[j] != NULL)
        gi_base_info_unref ((GIBaseInfo *)frame->out_tis[j]);
    }
  for (size_t k = 0; k < frame->n_gi_args; k++)
    {
      if (frame->in_len_ti[k] != NULL)
        gi_base_info_unref ((GIBaseInfo *)frame->in_len_ti[k]);
    }
  pygi_arg_cleanups_clear (frame->cleanups, frame->n_gi_args);
}
