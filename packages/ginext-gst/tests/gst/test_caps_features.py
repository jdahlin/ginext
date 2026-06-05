# Tests for Gst.CapsFeatures
#
# SPDX-License-Identifier: LGPL-2.0-or-later

from __future__ import annotations

import pytest
from ginext import Gst


class TestCapsFeatures:
    def test_new_empty(self) -> None:
        features = Gst.CapsFeatures()
        assert isinstance(features, Gst.CapsFeatures)
        assert len(features) == 0

    def test_new_from_string(self) -> None:
        features = Gst.CapsFeatures("memory:SystemMemory")
        assert len(features) == 1
        assert features[0] == "memory:SystemMemory"

    def test_new_from_existing(self) -> None:
        original = Gst.CapsFeatures("memory:SystemMemory")
        copied = Gst.CapsFeatures(original)
        assert copied is not original
        assert list(copied) == ["memory:SystemMemory"]

    def test_new_from_list(self) -> None:
        features = Gst.CapsFeatures(
            ["memory:SystemMemory", "meta:GstVideoOverlayComposition"]
        )
        assert list(features) == [
            "memory:SystemMemory",
            "meta:GstVideoOverlayComposition",
        ]

    def test_new_invalid(self) -> None:
        with pytest.raises(TypeError):
            Gst.CapsFeatures(42)

    def test_iter(self) -> None:
        features = Gst.CapsFeatures(
            ["memory:SystemMemory", "meta:GstVideoOverlayComposition"]
        )
        assert list(features) == [
            "memory:SystemMemory",
            "meta:GstVideoOverlayComposition",
        ]

    def test_getitem_negative_index(self) -> None:
        features = Gst.CapsFeatures(
            ["memory:SystemMemory", "meta:GstVideoOverlayComposition"]
        )
        assert features[-1] == "meta:GstVideoOverlayComposition"

    def test_getitem_out_of_range(self) -> None:
        features = Gst.CapsFeatures()
        with pytest.raises(IndexError):
            _ = features[0]

    def test_contains(self) -> None:
        features = Gst.CapsFeatures("memory:SystemMemory")
        assert "memory:SystemMemory" in features

    def test_repr(self) -> None:
        features = Gst.CapsFeatures("memory:SystemMemory")
        assert repr(features) == "<Gst.CapsFeatures ['memory:SystemMemory']>"

    def test_repr_any(self) -> None:
        features = Gst.CapsFeatures.new_any()
        assert repr(features) == "<Gst.CapsFeatures ANY>"
