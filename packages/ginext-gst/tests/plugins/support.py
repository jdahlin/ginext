# SPDX-License-Identifier: LGPL-2.1-or-later

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

from __future__ import annotations

import itertools
import json
import pathlib
import subprocess
import sys
import types
from typing import Any, Callable

ROOT = pathlib.Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from conftest_shared import setup_split_package_test_env

setup_split_package_test_env(ROOT)

import ginext

from ginext import Gst
from ginext.gobject.gobjectclass import GObject
from ginext.gobject.properties import Property
from ginext_gst import element, metadata as gst_metadata, pads

GstBase = ginext.GstBase
GstAudio = ginext.GstAudio
GstVideo = ginext.GstVideo
GstApp = ginext.GstApp
Gst.init(None)

__all__ = [
    "Gst",
    "GstApp",
    "GstAudio",
    "GstBase",
    "GstVideo",
    "Property",
    "any_caps",
    "author_aggregator_class",
    "author_audio_aggregator_class",
    "author_audio_decoder_class",
    "author_audio_encoder_class",
    "author_audio_filter_class",
    "author_audio_sink_class",
    "author_audio_src_class",
    "author_base_parse_class",
    "author_base_sink_class",
    "author_base_src_class",
    "author_element_class",
    "author_push_src_class",
    "author_request_class",
    "author_transform_chainup_send_event_class",
    "author_transform_class",
    "author_transform_with_property_signal_class",
    "author_video_aggregator_class",
    "author_video_decoder_class",
    "author_video_encoder_class",
    "author_video_filter_class",
    "encoded_audio_caps",
    "encoded_video_caps",
    "gst_bucket",
    "make_appsrc",
    "make_counting_appsink",
    "make_counting_fakesink",
    "make_pad_template",
    "make_request_sink_templates",
    "make_request_src_templates",
    "make_src_sink_templates",
    "push_buffers_and_eos",
    "raw_audio_caps",
    "raw_video_caps",
    "run_pipeline_to_eos",
    "run_subprocess_probe",
    "unique",
]

_counter = itertools.count()
_PLUGIN_METADATA = {
    "longname": "Python Probe",
    "classification": "Generic",
    "description": "probe",
    "author": "ginext",
}
_AUDIO_CAPS = Gst.Caps.from_string(
    "audio/x-raw,format=S16LE,rate=44100,channels=1,layout=interleaved"
)
_VIDEO_CAPS = Gst.Caps.from_string(
    "video/x-raw,format=RGBA,width=16,height=16,framerate=1/1"
)
_ENCODED_AUDIO_CAPS = Gst.Caps.from_string("audio/x-test")
_ENCODED_VIDEO_CAPS = Gst.Caps.from_string("video/x-test")
_ANY_CAPS = Gst.Caps.from_string("application/octet-stream")
assert _AUDIO_CAPS is not None
assert _VIDEO_CAPS is not None
assert _ENCODED_AUDIO_CAPS is not None
assert _ENCODED_VIDEO_CAPS is not None
assert _ANY_CAPS is not None


def unique(name: str) -> str:
    return f"Ginext{name}_{next(_counter)}"


def make_state(*keys: str) -> dict[str, int]:
    return {key: 0 for key in keys}


def raw_audio_caps() -> Any:
    caps = _AUDIO_CAPS
    assert caps is not None
    return caps.copy()


def raw_video_caps() -> Any:
    caps = _VIDEO_CAPS
    assert caps is not None
    return caps.copy()


def encoded_audio_caps() -> Any:
    caps = _ENCODED_AUDIO_CAPS
    assert caps is not None
    return caps.copy()


def encoded_video_caps() -> Any:
    caps = _ENCODED_VIDEO_CAPS
    assert caps is not None
    return caps.copy()


def any_caps() -> Any:
    caps = _ANY_CAPS
    assert caps is not None
    return caps.copy()


def make_pad_template(
    name: str,
    direction: Any,
    presence: Any,
    caps: Any,
    *,
    pad_type: Any | None = None,
) -> Any:
    if pad_type is None:
        return Gst.PadTemplate.new(name, direction, presence, caps)
    return Gst.PadTemplate.new_with_gtype(name, direction, presence, caps, pad_type)


def make_src_sink_templates(
    sink_caps: Any,
    src_caps: Any,
) -> list[Any]:
    return [
        make_pad_template(
            "sink", Gst.PadDirection.SINK, Gst.PadPresence.ALWAYS, sink_caps
        ),
        make_pad_template(
            "src", Gst.PadDirection.SRC, Gst.PadPresence.ALWAYS, src_caps
        ),
    ]


def make_request_src_templates(
    sink_caps: Any,
    src_caps: Any,
    src_name: str = "src_%u",
) -> list[Any]:
    return [
        make_pad_template(
            "sink", Gst.PadDirection.SINK, Gst.PadPresence.ALWAYS, sink_caps
        ),
        make_pad_template(
            src_name, Gst.PadDirection.SRC, Gst.PadPresence.REQUEST, src_caps
        ),
    ]


def make_request_sink_templates(
    sink_caps: Any,
    src_caps: Any,
    sink_name: str = "sink_%u",
    *,
    sink_pad_type: Any | None = None,
    src_pad_type: Any | None = None,
) -> list[Any]:
    return [
        make_pad_template(
            sink_name,
            Gst.PadDirection.SINK,
            Gst.PadPresence.REQUEST,
            sink_caps,
            pad_type=sink_pad_type,
        ),
        make_pad_template(
            "src",
            Gst.PadDirection.SRC,
            Gst.PadPresence.ALWAYS,
            src_caps,
            pad_type=src_pad_type,
        ),
    ]


def count_call(
    state: dict[str, int],
    key: str,
    *,
    return_value: Any = None,
    chainup: Callable[..., Any] | None = None,
) -> Callable[..., Any]:
    def impl(self: Any, *args: Any) -> Any:
        state[key] = state.get(key, 0) + 1
        if chainup is not None:
            return chainup(self, *args)
        return return_value

    return impl


def register_element_class(
    cls: type[Any],
    *,
    element_name: str,
    metadata: dict[str, str] | None = None,
    pad_templates: list[Any] | None = None,
    rank: Any = None,
) -> type[Any]:
    details = dict(_PLUGIN_METADATA if metadata is None else metadata)
    cls = gst_metadata(
        details["longname"],
        details["classification"],
        details["description"],
        details["author"],
    )(cls)
    cls = pads(*(pad_templates or []))(cls)
    return element(element_name, rank=rank)(cls)


def gst_bucket(cls: type[Any]) -> dict[str, Any]:
    bucket = cls.gimeta.extensions["Gst"]
    assert isinstance(bucket, dict)
    return bucket


def author_element_class(
    *,
    base_cls: type[Any],
    type_name: str,
    element_name: str,
    methods: dict[str, Any],
    metadata: dict[str, str] | None = None,
    pad_templates: list[Any] | None = None,
    python_name: str | None = None,
) -> type[Any]:
    class_body = {
        "__module__": __name__,
        **methods,
    }
    cls = types.new_class(
        python_name or type_name,
        (base_cls,),
        {},
        lambda ns: ns.update(class_body),
    )
    return register_element_class(
        cls,
        element_name=element_name,
        metadata=metadata,
        pad_templates=pad_templates,
    )


def run_pipeline_to_eos(pipe: Any, *, timeout: int | None = None) -> Any:
    if isinstance(pipe, str):
        pipe = Gst.parse_launch(pipe)
    timeout = 5 * Gst.SECOND if timeout is None else timeout
    try:
        assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
        msg = pipe.get_bus().timed_pop_filtered(
            timeout, Gst.MessageType.EOS | Gst.MessageType.ERROR
        )
        assert msg is not None
        assert msg.type != Gst.MessageType.ERROR
        return msg
    finally:
        pipe.set_state(Gst.State.NULL)


def make_counting_fakesink(
    state: dict[str, int],
    *,
    signal_key: str = "handoff",
) -> Any:
    sink = Gst.ElementFactory.make("fakesink", unique("probe_sink"))
    sink.signal_handoffs = True

    def on_handoff(*_args: Any) -> None:
        state[signal_key] += 1

    sink.connect("handoff", on_handoff)
    return sink


def make_counting_appsink(
    state: dict[str, int],
    *,
    signal_key: str = "new_sample",
) -> Any:
    sink = Gst.ElementFactory.make("appsink", unique("probe_appsink"))
    sink.emit_signals = True
    sink.sync = False

    def on_new_sample(appsink: Any) -> Any:
        state[signal_key] += 1
        sample = appsink.pull_sample()
        assert sample is not None
        return Gst.FlowReturn.OK

    sink.connect("new-sample", on_new_sample)
    return sink


def make_appsrc(
    *,
    caps: Any,
    name: str | None = None,
) -> Any:
    src = Gst.ElementFactory.make("appsrc", name or unique("probe_appsrc"))
    src.caps = caps
    src.format = Gst.Format.TIME
    src.is_live = False
    return src


def push_buffers_and_eos(appsrc: Any, payloads: list[bytes]) -> None:
    for payload in payloads:
        buf = Gst.Buffer.new_allocate(None, len(payload), None)
        buf.fill(0, list(payload))
        assert appsrc.push_buffer(buf) == Gst.FlowReturn.OK
    appsrc.end_of_stream()


def run_subprocess_probe(
    module_file: str,
    probe_name: str,
    *,
    timeout: int = 5,
    **kwargs: Any,
) -> Any:
    module_path = pathlib.Path(module_file).resolve()
    package_root = module_path.parents[2]
    module_name = ".".join(module_path.relative_to(package_root).with_suffix("").parts)
    runner = pathlib.Path(__file__).with_name("subprocess_runner.py")
    proc = subprocess.run(
        [
            sys.executable,
            str(runner),
            str(package_root),
            module_name,
            probe_name,
            json.dumps(kwargs),
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(proc.stdout.strip())


def author_transform_class(
    *,
    type_name: str,
    element_name: str,
    state: dict[str, int],
) -> type[Any]:
    def do_base_transform_query(self: Any, direction: Any, query: Any) -> Any:
        state["query"] = state.get("query", 0) + 1
        return GstBase.BaseTransform.do_query(self, direction, query)

    return author_element_class(
        base_cls=GstBase.BaseTransform,
        type_name=type_name,
        element_name=element_name,
        methods={
            "do_transform_ip": count_call(
                state, "transform_ip", return_value=Gst.FlowReturn.OK
            ),
            "do_change_state": count_call(
                state,
                "change_state",
                chainup=GstBase.BaseTransform.do_change_state,
            ),
            "do_send_event": count_call(state, "send_event", return_value=True),
            "do_base_transform_query": do_base_transform_query,
        },
        metadata={
            "longname": "Python Transform",
            "classification": "Filter/Effect",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=make_src_sink_templates(raw_audio_caps(), raw_audio_caps()),
    )


def author_transform_chainup_send_event_class(
    *,
    type_name: str,
    element_name: str,
    state: dict[str, int],
) -> type[Any]:
    return author_element_class(
        base_cls=GstBase.BaseTransform,
        type_name=type_name,
        element_name=element_name,
        methods={
            "do_send_event": count_call(
                state,
                "send_event",
                chainup=GstBase.BaseTransform.do_send_event,
            ),
        },
        metadata={
            "longname": "Python Transform Chainup",
            "classification": "Filter/Effect",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=make_src_sink_templates(raw_audio_caps(), raw_audio_caps()),
    )


def author_request_class(
    *,
    type_name: str,
    element_name: str,
    state: dict[str, int],
) -> type[Any]:
    def do_request_new_pad(self: Any, templ: Any, name: str | None, caps: Any) -> Any:
        state["request_new_pad"] += 1
        pad = Gst.Pad.new_from_template(
            templ, name or f"src_{state['request_new_pad']}"
        )
        self.add_pad(pad)
        return pad

    def do_release_pad(self: Any, pad: Any) -> None:
        state["release_pad"] += 1
        self.remove_pad(pad)

    return author_element_class(
        base_cls=Gst.Element,
        type_name=type_name,
        element_name=element_name,
        methods={
            "do_request_new_pad": do_request_new_pad,
            "do_release_pad": do_release_pad,
        },
        metadata={
            "longname": "Python Request",
            "classification": "Generic",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=make_request_src_templates(any_caps(), any_caps()),
    )


def author_transform_with_property_signal_class(
    *,
    type_name: str,
    element_name: str,
    state: dict[str, int],
) -> type[Any]:
    def do_start(self: Any) -> bool:
        state["start"] += 1
        return True

    def do_stop(self: Any) -> bool:
        state["stop"] += 1
        return True

    def do_transform_ip(self: Any, buf: Any) -> Gst.FlowReturn:
        self.pinged.emit(self.level)
        return Gst.FlowReturn.OK

    transform = author_element_class(
        base_cls=GstBase.BaseTransform,
        type_name=type_name,
        element_name=element_name,
        methods={
            "__annotations__": {"level": int},
            "level": Property(default=7),
            "pinged": GObject.Signal(int),
            "do_start": do_start,
            "do_stop": do_stop,
            "do_transform_ip": do_transform_ip,
        },
        metadata={
            "longname": "Python Transform Property Signal",
            "classification": "Filter/Effect",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=make_src_sink_templates(raw_audio_caps(), raw_audio_caps()),
    )
    return transform


def author_audio_filter_class(
    *,
    type_name: str,
    element_name: str,
    state: dict[str, int],
) -> type[Any]:
    return author_element_class(
        base_cls=GstAudio.AudioFilter,
        type_name=type_name,
        element_name=element_name,
        methods={
            "do_setup": count_call(state, "setup", return_value=True),
            "do_transform_ip": count_call(
                state, "transform_ip", return_value=Gst.FlowReturn.OK
            ),
        },
        metadata={
            "longname": "Python Audio Filter",
            "classification": "Filter/Effect/Audio",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=make_src_sink_templates(raw_audio_caps(), raw_audio_caps()),
    )


def author_video_filter_class(
    *,
    type_name: str,
    element_name: str,
    state: dict[str, int],
) -> type[Any]:
    return author_element_class(
        base_cls=GstVideo.VideoFilter,
        type_name=type_name,
        element_name=element_name,
        methods={
            "do_set_info": count_call(state, "set_info", return_value=True),
            "do_transform_frame_ip": count_call(
                state, "transform_frame_ip", return_value=Gst.FlowReturn.OK
            ),
        },
        metadata={
            "longname": "Python Video Filter",
            "classification": "Filter/Effect/Video",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=make_src_sink_templates(raw_video_caps(), raw_video_caps()),
    )


def author_audio_src_class(
    *,
    type_name: str,
    element_name: str,
    state: dict[str, int],
) -> type[Any]:
    return author_element_class(
        base_cls=GstAudio.AudioSrc,
        type_name=type_name,
        element_name=element_name,
        methods={
            "do_open": count_call(state, "open", return_value=True),
            "do_prepare": count_call(state, "prepare", return_value=True),
            "do_read": count_call(state, "read", return_value=(0, 0)),
            "do_reset": count_call(state, "reset", return_value=None),
            "do_unprepare": count_call(state, "unprepare", return_value=True),
            "do_close": count_call(state, "close", return_value=True),
            "do_delay": count_call(state, "delay", return_value=0),
        },
        metadata={
            "longname": "Python Audio Src",
            "classification": "Source/Audio",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=[
            make_pad_template(
                "src", Gst.PadDirection.SRC, Gst.PadPresence.ALWAYS, raw_audio_caps()
            )
        ],
    )


def author_audio_sink_class(
    *,
    type_name: str,
    element_name: str,
    state: dict[str, int],
) -> type[Any]:
    return author_element_class(
        base_cls=GstAudio.AudioSink,
        type_name=type_name,
        element_name=element_name,
        methods={
            "do_open": count_call(state, "open", return_value=True),
            "do_audio_sink_prepare": count_call(state, "prepare", return_value=True),
            "do_audio_sink_write": count_call(state, "write", return_value=0),
            "do_delay": count_call(state, "delay", return_value=0),
            "do_reset": count_call(state, "reset", return_value=None),
            "do_unprepare": count_call(state, "unprepare", return_value=True),
            "do_close": count_call(state, "close", return_value=True),
        },
        metadata={
            "longname": "Python Audio Sink",
            "classification": "Sink/Audio",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=[
            make_pad_template(
                "sink", Gst.PadDirection.SINK, Gst.PadPresence.ALWAYS, raw_audio_caps()
            )
        ],
    )


def author_base_src_class(
    *,
    type_name: str,
    element_name: str,
    state: dict[str, int],
) -> type[Any]:
    return author_element_class(
        base_cls=GstBase.BaseSrc,
        type_name=type_name,
        element_name=element_name,
        methods={
            "do_start": count_call(state, "start", return_value=True),
            "do_stop": count_call(state, "stop", return_value=True),
            "do_is_seekable": count_call(state, "is_seekable", return_value=False),
            "do_create": count_call(
                state, "create", return_value=(Gst.FlowReturn.EOS, None)
            ),
        },
        metadata={
            "longname": "Python Base Src",
            "classification": "Source",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=[
            make_pad_template(
                "src", Gst.PadDirection.SRC, Gst.PadPresence.ALWAYS, any_caps()
            )
        ],
    )


def author_push_src_class(
    *,
    type_name: str,
    element_name: str,
    state: dict[str, int],
) -> type[Any]:
    return author_element_class(
        base_cls=GstBase.PushSrc,
        type_name=type_name,
        element_name=element_name,
        methods={
            "do_start": count_call(state, "start", return_value=True),
            "do_stop": count_call(state, "stop", return_value=True),
            "do_push_src_create": count_call(
                state, "create", return_value=(Gst.FlowReturn.EOS, None)
            ),
        },
        metadata={
            "longname": "Python Push Src",
            "classification": "Source",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=[
            make_pad_template(
                "src", Gst.PadDirection.SRC, Gst.PadPresence.ALWAYS, any_caps()
            )
        ],
    )


def author_base_sink_class(
    *,
    type_name: str,
    element_name: str,
    state: dict[str, int],
) -> type[Any]:
    return author_element_class(
        base_cls=GstBase.BaseSink,
        type_name=type_name,
        element_name=element_name,
        methods={
            "do_start": count_call(state, "start", return_value=True),
            "do_stop": count_call(state, "stop", return_value=True),
            "do_render": count_call(state, "render", return_value=Gst.FlowReturn.OK),
            "do_preroll": count_call(state, "preroll", return_value=Gst.FlowReturn.OK),
        },
        metadata={
            "longname": "Python Base Sink",
            "classification": "Sink",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=[
            make_pad_template(
                "sink", Gst.PadDirection.SINK, Gst.PadPresence.ALWAYS, any_caps()
            )
        ],
    )


def author_base_parse_class(
    *,
    type_name: str,
    element_name: str,
    state: dict[str, int],
) -> type[Any]:
    return author_element_class(
        base_cls=GstBase.BaseParse,
        type_name=type_name,
        element_name=element_name,
        methods={
            "do_start": count_call(state, "start", return_value=True),
            "do_stop": count_call(state, "stop", return_value=True),
            "do_handle_frame": count_call(
                state, "handle_frame", return_value=Gst.FlowReturn.EOS
            ),
        },
        metadata={
            "longname": "Python Base Parse",
            "classification": "Codec/Parser",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=make_src_sink_templates(any_caps(), any_caps()),
    )


def author_aggregator_class(
    *,
    type_name: str,
    element_name: str,
    state: dict[str, int],
) -> type[Any]:
    return author_element_class(
        base_cls=GstBase.Aggregator,
        type_name=type_name,
        element_name=element_name,
        methods={
            "do_aggregate": count_call(
                state, "aggregate", return_value=Gst.FlowReturn.OK
            ),
        },
        metadata={
            "longname": "Python Aggregator",
            "classification": "Generic",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=make_request_sink_templates(any_caps(), any_caps(), "sink_%u"),
    )


def author_audio_decoder_class(
    *,
    type_name: str,
    element_name: str,
    state: dict[str, int],
) -> type[Any]:
    return author_element_class(
        base_cls=GstAudio.AudioDecoder,
        type_name=type_name,
        element_name=element_name,
        methods={
            "do_start": count_call(state, "start", return_value=True),
            "do_stop": count_call(state, "stop", return_value=True),
            "do_set_format": count_call(state, "set_format", return_value=True),
            "do_handle_frame": count_call(
                state, "handle_frame", return_value=Gst.FlowReturn.OK
            ),
        },
        metadata={
            "longname": "Python Audio Decoder",
            "classification": "Decoder/Audio",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=make_src_sink_templates(encoded_audio_caps(), raw_audio_caps()),
    )


def author_audio_encoder_class(
    *,
    type_name: str,
    element_name: str,
    state: dict[str, int],
) -> type[Any]:
    return author_element_class(
        base_cls=GstAudio.AudioEncoder,
        type_name=type_name,
        element_name=element_name,
        methods={
            "do_start": count_call(state, "start", return_value=True),
            "do_stop": count_call(state, "stop", return_value=True),
            "do_set_format": count_call(state, "set_format", return_value=True),
            "do_handle_frame": count_call(
                state, "handle_frame", return_value=Gst.FlowReturn.OK
            ),
        },
        metadata={
            "longname": "Python Audio Encoder",
            "classification": "Encoder/Audio",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=make_src_sink_templates(raw_audio_caps(), encoded_audio_caps()),
    )


def author_audio_aggregator_class(
    *,
    type_name: str,
    element_name: str,
    state: dict[str, int],
) -> type[Any]:
    return author_element_class(
        base_cls=GstAudio.AudioAggregator,
        type_name=type_name,
        element_name=element_name,
        methods={
            "do_aggregate_one_buffer": count_call(
                state, "aggregate", return_value=True
            ),
        },
        metadata={
            "longname": "Python Audio Aggregator",
            "classification": "Filter/Mixer/Audio",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=make_request_sink_templates(
            raw_audio_caps(),
            raw_audio_caps(),
            "sink_%u",
            sink_pad_type=GstAudio.AudioAggregatorPad,
            src_pad_type=GstAudio.AudioAggregatorPad,
        ),
    )


def author_video_sink_class(
    *,
    type_name: str,
    element_name: str,
    state: dict[str, int],
) -> type[Any]:
    return author_element_class(
        base_cls=GstVideo.VideoSink,
        type_name=type_name,
        element_name=element_name,
        methods={
            "do_set_info": count_call(state, "set_info", return_value=True),
            "do_show_frame": count_call(
                state, "show_frame", return_value=Gst.FlowReturn.OK
            ),
        },
        metadata={
            "longname": "Python Video Sink",
            "classification": "Sink/Video",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=[
            make_pad_template(
                "sink", Gst.PadDirection.SINK, Gst.PadPresence.ALWAYS, raw_video_caps()
            )
        ],
    )


def author_video_decoder_class(
    *,
    type_name: str,
    element_name: str,
    state: dict[str, int],
) -> type[Any]:
    return author_element_class(
        base_cls=GstVideo.VideoDecoder,
        type_name=type_name,
        element_name=element_name,
        methods={
            "do_start": count_call(state, "start", return_value=True),
            "do_stop": count_call(state, "stop", return_value=True),
            "do_set_format": count_call(state, "set_format", return_value=True),
            "do_handle_frame": count_call(
                state, "handle_frame", return_value=Gst.FlowReturn.OK
            ),
        },
        metadata={
            "longname": "Python Video Decoder",
            "classification": "Decoder/Video",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=make_src_sink_templates(encoded_video_caps(), raw_video_caps()),
    )


def author_video_encoder_class(
    *,
    type_name: str,
    element_name: str,
    state: dict[str, int],
) -> type[Any]:
    return author_element_class(
        base_cls=GstVideo.VideoEncoder,
        type_name=type_name,
        element_name=element_name,
        methods={
            "do_start": count_call(state, "start", return_value=True),
            "do_stop": count_call(state, "stop", return_value=True),
            "do_set_format": count_call(state, "set_format", return_value=True),
            "do_handle_frame": count_call(
                state, "handle_frame", return_value=Gst.FlowReturn.OK
            ),
        },
        metadata={
            "longname": "Python Video Encoder",
            "classification": "Encoder/Video",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=make_src_sink_templates(raw_video_caps(), encoded_video_caps()),
    )


def author_video_aggregator_class(
    *,
    type_name: str,
    element_name: str,
    state: dict[str, int],
) -> type[Any]:
    return author_element_class(
        base_cls=GstVideo.VideoAggregator,
        type_name=type_name,
        element_name=element_name,
        methods={
            "do_aggregate_frames": count_call(
                state, "aggregate_frames", return_value=Gst.FlowReturn.OK
            ),
        },
        metadata={
            "longname": "Python Video Aggregator",
            "classification": "Filter/Mixer/Video",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=make_request_sink_templates(
            raw_video_caps(),
            raw_video_caps(),
            "sink_%u",
            sink_pad_type=GstVideo.VideoAggregatorPad,
        ),
    )
