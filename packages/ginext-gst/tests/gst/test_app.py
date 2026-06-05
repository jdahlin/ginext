# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import pytest
from ginext import Gst, GstApp


def _wait_for_terminal_message(pipe: Gst.Pipeline) -> Gst.Message:
    bus = pipe.get_bus()
    assert bus is not None
    message = bus.timed_pop_filtered(
        5 * Gst.SECOND,
        Gst.MessageType.EOS | Gst.MessageType.ERROR,
    )
    assert message is not None
    assert message.type != Gst.MessageType.ERROR
    return message


def _buffer_from_payload(payload: bytes) -> Gst.Buffer:
    buf = Gst.Buffer.new_allocate(None, len(payload), None)
    buf.fill(0, list(payload))
    return buf


def _sample_payload(sample: Gst.Sample) -> bytes:
    out = sample.get_buffer()
    assert out is not None
    ok, info = out.map(Gst.MapFlags.READ)
    assert ok is True
    try:
        return bytes(info.data)
    finally:
        out.unmap(info)


def _make_appsrc_pipeline() -> tuple[Gst.Pipeline, GstApp.AppSrc, GstApp.AppSink]:
    pipe = Gst.Pipeline()
    src = GstApp.AppSrc()
    identity = Gst.ElementFactory.make("identity", "identity")
    assert identity is not None
    sink = GstApp.AppSink()

    sink.sync = False
    sink.emit_signals = False
    caps = Gst.Caps.from_string("application/octet-stream")
    assert caps is not None
    src.caps = caps
    src.format = Gst.Format.TIME

    pipe.add(src)
    pipe.add(identity)
    pipe.add(sink)
    assert src.link(identity) is True
    assert identity.link(sink) is True
    return pipe, src, sink


@pytest.mark.parametrize(
    ("push", "payloads"),
    [
        ("buffer", [b"ping"]),
        ("sample", [b"pong"]),
        ("buffer_list", [b"ab", b"cd"]),
    ],
)
def test_appsrc_push_variants_deliver_payloads(
    push: str,
    payloads: list[bytes],
) -> None:
    pipe, src, sink = _make_appsrc_pipeline()

    assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
    try:
        if push == "buffer":
            assert (
                src.push_buffer(_buffer_from_payload(payloads[0])) == Gst.FlowReturn.OK
            )
        elif push == "sample":
            sample = Gst.Sample.new(
                _buffer_from_payload(payloads[0]),
                Gst.Caps.from_string("application/octet-stream"),
                None,
                None,
            )
            assert src.push_sample(sample) == Gst.FlowReturn.OK
        else:
            buffer_list = Gst.BufferList.new_sized(len(payloads))
            for payload in payloads:
                buffer_list.insert(-1, _buffer_from_payload(payload))
            assert src.push_buffer_list(buffer_list) == Gst.FlowReturn.OK

        assert src.end_of_stream() == Gst.FlowReturn.OK

        seen = []
        for payload in payloads:
            pulled_sample = sink.try_pull_sample(5 * Gst.SECOND)
            assert pulled_sample is not None
            seen.append(_sample_payload(pulled_sample))
        assert seen == payloads

        assert src.get_current_level_bytes() == 0
        assert src.get_current_level_buffers() == 0
        message = _wait_for_terminal_message(pipe)
        assert message.type == Gst.MessageType.EOS
    finally:
        pipe.set_state(Gst.State.NULL)


def test_appsink_new_sample_signal_pulls_data() -> None:
    pipe = Gst.Pipeline()
    src = Gst.ElementFactory.make("audiotestsrc", "src")
    assert src is not None
    sink = GstApp.AppSink()

    src.num_buffers = 1
    src.samplesperbuffer = 16
    caps = Gst.Caps.from_string("audio/x-raw,format=S16LE,channels=1,rate=44100")
    assert caps is not None
    sink.caps = caps
    sink.emit_signals = True
    sink.sync = False

    seen: list[bytes] = []

    def on_new_sample(appsink: GstApp.AppSink) -> Gst.FlowReturn:
        sample = appsink.pull_sample()
        assert sample is not None
        seen.append(_sample_payload(sample))
        return Gst.FlowReturn.OK

    conn = sink.new_sample.connect(on_new_sample, owner=sink)

    pipe.add(src)
    pipe.add(sink)
    assert src.link(sink) is True

    assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
    try:
        message = _wait_for_terminal_message(pipe)
        assert message.type == Gst.MessageType.EOS
        assert sink.is_eos() is True
        caps = sink.get_caps()
        assert caps is not None
        assert (
            caps.to_string()
            == "audio/x-raw, format=(string)S16LE, channels=(int)1, rate=(int)44100"
        )
        assert len(seen) == 1
        assert seen[0] != b""
    finally:
        pipe.set_state(Gst.State.NULL)
        conn.disconnect()


def test_appsink_preroll_and_buffer_list_support() -> None:
    pipe = Gst.Pipeline()
    src = Gst.ElementFactory.make("audiotestsrc", "src")
    assert src is not None
    sink = GstApp.AppSink()

    src.num_buffers = 1
    src.samplesperbuffer = 16
    sink.sync = False
    sink.emit_signals = False

    assert sink.get_buffer_list_support() is False
    sink.set_buffer_list_support(True)
    assert sink.get_buffer_list_support() is True

    pipe.add(src)
    pipe.add(sink)
    assert src.link(sink) is True

    assert pipe.set_state(Gst.State.PAUSED) != Gst.StateChangeReturn.FAILURE
    try:
        preroll_sample = sink.try_pull_preroll(5 * Gst.SECOND)
        assert preroll_sample is not None
        assert _sample_payload(preroll_sample) != b""

        assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
        sample = sink.try_pull_sample(5 * Gst.SECOND)
        assert sample is not None
        assert _sample_payload(sample) != b""
        message = _wait_for_terminal_message(pipe)
        assert message.type == Gst.MessageType.EOS
        assert sink.is_eos() is True
    finally:
        pipe.set_state(Gst.State.NULL)
