# SPDX-License-Identifier: LGPL-2.1-or-later

"""Tests for the GstBase.CollectPads helper surface."""

from __future__ import annotations

import ginext
from ginext import Gst

GstBase = ginext.GstBase


def test_collectpads_helper_type_is_available() -> None:
    """Confirms the helper type is introspected and exposed to Python."""
    assert GstBase.CollectPads.gimeta.gtype != 0


def test_collectpads_exposes_expected_helper_methods() -> None:
    """Checks the basic helper entry points needed by future muxer-style tests."""
    names = dir(GstBase.CollectPads)
    assert "add_pad" in names
    assert "remove_pad" in names
    assert "available" in names
    assert "peek" in names
    assert "pop" in names
    assert "flush" in names
    assert "start" in names
    assert "stop" in names


def test_collectpads_callback_setters_accept_python_callables() -> None:
    """Verifies the Python callback registration surface is exposed."""
    helper = GstBase.CollectPads()
    helper.set_function(lambda *args: True)
    helper.set_buffer_function(lambda *args: None)
    helper.set_compare_function(lambda *args: 0)
    helper.set_event_function(lambda *args: True)
    helper.set_query_function(lambda *args: True)
    helper.set_clip_function(lambda *args: None)
    helper.set_flush_function(lambda *args: None)


def test_collectpads_empty_helper_reports_no_available_data() -> None:
    """Checks the empty helper state before any sink pads are added."""
    helper = GstBase.CollectPads()
    assert helper.available() == 0


def test_collectpads_supports_collectdata_lifecycle_when_given_explicit_size() -> None:
    """Verifies the low-level add-pad calling convention and helper lifecycle."""
    helper = GstBase.CollectPads()
    pad = Gst.Pad.new("sink0", Gst.PadDirection.SINK)

    data = helper.add_pad(pad, 256, None, True)
    helper.start()
    helper.stop()

    assert type(data).__name__ == "CollectData"
    assert helper.available() == 0
    assert helper.peek(data) is None
    assert helper.pop(data) is None
    assert helper.flush(data, 0) == 0
    assert helper.remove_pad(pad) is True


def test_collectpads_exposes_waiting_and_flushing_controls() -> None:
    """Checks the helper-wide flow-control toggles used by muxer-style code."""
    helper = GstBase.CollectPads()
    pad = Gst.Pad.new("sink0", Gst.PadDirection.SINK)
    data = helper.add_pad(pad, 256, None, True)

    helper.set_waiting(data, True)
    helper.set_waiting(data, False)
    helper.set_flushing(True)
    helper.set_flushing(False)

    assert helper.remove_pad(pad) is True


def test_collectpads_pad_data_methods_require_collect_data_arguments() -> None:
    """Checks the current Python call shape for per-pad helper methods."""
    helper = GstBase.CollectPads()

    try:
        helper.peek()
    except TypeError as exc:
        assert "peek() takes exactly 2 arguments" in str(exc)
    else:
        raise AssertionError("peek() unexpectedly accepted no collect-data argument")

    try:
        helper.pop()
    except TypeError as exc:
        assert "pop() takes exactly 2 arguments" in str(exc)
    else:
        raise AssertionError("pop() unexpectedly accepted no collect-data argument")

    try:
        helper.flush()
    except TypeError as exc:
        assert "flush() takes exactly 3 arguments" in str(exc)
    else:
        raise AssertionError("flush() unexpectedly accepted no collect-data arguments")
