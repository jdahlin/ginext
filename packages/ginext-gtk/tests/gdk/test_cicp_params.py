# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Gdk


def test_cicp_params_exposes_basic_record_fields() -> None:
    params = Gdk.CicpParams()
    params.color_primaries = 1
    params.transfer_function = 2
    params.matrix_coefficients = 3
    params.range = 1

    assert params.color_primaries == 1
    assert params.transfer_function == 2
    assert params.matrix_coefficients == 3
    assert params.range == 1
