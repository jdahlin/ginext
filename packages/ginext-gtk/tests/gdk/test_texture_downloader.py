# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import pytest

from .support import make_texture, run_subprocess_probe


def test_texture_downloader_returns_bytes_and_stride() -> None:
    texture = make_texture()
    from ginext import Gdk

    loader = Gdk.TextureDownloader.new(texture)
    result = loader.download_bytes()

    assert loader.get_texture() is texture
    assert result.out_stride == 4
    assert result[0].get_size() == 4


def probe_texture_downloader_copy() -> bool:
    from ginext import Gdk

    copy = Gdk.TextureDownloader.new(make_texture()).copy()
    assert copy is not None
    assert copy.get_texture() is not None
    return True


def test_texture_downloader_copy_returns_another_downloader() -> None:
    assert run_subprocess_probe(__file__, "probe_texture_downloader_copy") is True


def probe_texture_downloader_planes() -> int:
    from ginext import Gdk

    result = Gdk.TextureDownloader.new(make_texture()).download_bytes_with_planes()
    return int(result.out_stride)


@pytest.mark.xfail(
    reason="Gdk.TextureDownloader.download_bytes_with_planes currently corrupts allocator state",
    strict=True,
)
def test_texture_downloader_download_bytes_with_planes_reports_stride() -> None:
    assert run_subprocess_probe(__file__, "probe_texture_downloader_planes") == 4
