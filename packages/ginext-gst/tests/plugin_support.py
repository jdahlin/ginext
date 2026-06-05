# SPDX-License-Identifier: LGPL-2.1-or-later

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

from __future__ import annotations

import itertools
import types
from typing import Any

from ginext import Gst, GstBase
from ginext.gobject.gobjectclass import GObject
from ginext.gobject.properties import Property

Gst.init(None)

_counter = itertools.count()
_AUDIO_CAPS = Gst.Caps.from_string(
    "audio/x-raw,format=S16LE,rate=44100,channels=1,layout=interleaved"
)
_ANY_CAPS = Gst.Caps.from_string("application/octet-stream")
_VIDEO_CAPS = Gst.Caps.from_string(
    "video/x-raw,format=RGBA,width=16,height=16,framerate=1/1"
)
_ENCODED_AUDIO_CAPS = Gst.Caps.from_string("audio/x-test-custom")
_ENCODED_VIDEO_CAPS = Gst.Caps.from_string("video/x-test-custom")
assert _AUDIO_CAPS is not None
assert _ANY_CAPS is not None
assert _VIDEO_CAPS is not None
assert _ENCODED_AUDIO_CAPS is not None
assert _ENCODED_VIDEO_CAPS is not None


def unique(name: str) -> str:
    return f"Ginext{name}_{next(_counter)}"


def gst_bucket(cls: type[Any]) -> dict[str, Any]:
    bucket = cls.gimeta.extensions["Gst"]
    assert isinstance(bucket, dict)
    return bucket


def define_subclass(
    base_cls: type[Any],
    *,
    type_name: str,
    attrs: dict[str, object] | None = None,
    class_name: str = "Authored",
) -> type[Any]:
    authored = types.new_class(
        class_name,
        (base_cls,),
        {"kwds": {"type_name": type_name}},
        lambda ns: ns.update({"__module__": __name__}),
    )
    if attrs is not None:
        for key, value in attrs.items():
            setattr(authored, key, value)
    return authored


def register_authored_element(
    base_cls: type[Any],
    *,
    type_name: str,
    element_name: str,
    metadata: tuple[str, str, str, str],
    pad_templates: list[tuple[str, Any, Any, Any]],
    attrs: dict[str, object] | None = None,
    class_name: str = "Authored",
) -> type[Any]:
    cls = define_subclass(
        base_cls, type_name=type_name, attrs=attrs, class_name=class_name
    )
    cls.set_metadata(*metadata)
    for name, direction, presence, caps in pad_templates:
        cls.add_pad_template(Gst.PadTemplate.new(name, direction, presence, caps))
    assert Gst.Element.register(None, element_name, Gst.Rank.NONE, cls) is True
    return cls


def author_transform_class(
    *,
    type_name: str,
    element_name: str,
    state: dict[str, int],
) -> type[Any]:
    def do_transform_ip(self: Any, buf: Any) -> Gst.FlowReturn:
        state["transform_ip"] += 1
        return Gst.FlowReturn.OK

    def do_change_state(self: Any, transition: Any) -> Any:
        state["change_state"] += 1
        return GstBase.BaseTransform.do_change_state(self, transition)

    def do_send_event(self: Any, event: Any) -> bool:
        state["send_event"] += 1
        return True

    def do_query(self: Any, direction: Any, query: Any) -> Any:
        state["query"] += 1
        return GstBase.BaseTransform.do_query(self, direction, query)

    transform = define_subclass(
        GstBase.BaseTransform,
        type_name=type_name,
        attrs={
            "do_transform_ip": do_transform_ip,
            "do_change_state": do_change_state,
            "do_send_event": do_send_event,
            "do_query": do_query,
        },
        class_name="Transform",
    )
    transform.set_metadata("Python Transform", "Filter/Effect", "probe", "ginext")
    transform.add_pad_template(
        Gst.PadTemplate.new(
            "sink", Gst.PadDirection.SINK, Gst.PadPresence.ALWAYS, _AUDIO_CAPS
        )
    )
    transform.add_pad_template(
        Gst.PadTemplate.new(
            "src", Gst.PadDirection.SRC, Gst.PadPresence.ALWAYS, _AUDIO_CAPS
        )
    )
    assert Gst.Element.register(None, element_name, Gst.Rank.NONE, transform) is True
    return transform


def author_transform_chainup_send_event_class(
    *,
    type_name: str,
    element_name: str,
    state: dict[str, int],
) -> type[Any]:
    def do_send_event(self: Any, event: Any) -> Any:
        state["send_event"] += 1
        return GstBase.BaseTransform.do_send_event(self, event)

    transform = define_subclass(
        GstBase.BaseTransform,
        type_name=type_name,
        attrs={"do_send_event": do_send_event},
        class_name="Transform",
    )
    transform.set_metadata(
        "Python Transform Chainup", "Filter/Effect", "probe", "ginext"
    )
    transform.add_pad_template(
        Gst.PadTemplate.new(
            "sink", Gst.PadDirection.SINK, Gst.PadPresence.ALWAYS, _AUDIO_CAPS
        )
    )
    transform.add_pad_template(
        Gst.PadTemplate.new(
            "src", Gst.PadDirection.SRC, Gst.PadPresence.ALWAYS, _AUDIO_CAPS
        )
    )
    assert Gst.Element.register(None, element_name, Gst.Rank.NONE, transform) is True
    return transform


def author_request_class(
    *,
    type_name: str,
    element_name: str,
    state: dict[str, int],
) -> type[Any]:
    def do_request_new_pad(
        self: Any,
        templ: Any,
        name: str | None,
        caps: Any,
    ) -> Any:
        state["request_new_pad"] += 1
        pad = Gst.Pad.new_from_template(
            templ, name or f"src_{state['request_new_pad']}"
        )
        self.add_pad(pad)
        return pad

    def do_release_pad(self: Any, pad: Any) -> None:
        state["release_pad"] += 1
        self.remove_pad(pad)

    request_element = define_subclass(
        Gst.Element,
        type_name=type_name,
        attrs={
            "do_request_new_pad": do_request_new_pad,
            "do_release_pad": do_release_pad,
        },
        class_name="RequestElement",
    )
    request_element.set_metadata("Python Request", "Generic", "probe", "ginext")
    request_element.add_pad_template(
        Gst.PadTemplate.new(
            "sink", Gst.PadDirection.SINK, Gst.PadPresence.ALWAYS, _ANY_CAPS
        )
    )
    request_element.add_pad_template(
        Gst.PadTemplate.new(
            "src_%u", Gst.PadDirection.SRC, Gst.PadPresence.REQUEST, _ANY_CAPS
        )
    )
    assert (
        Gst.Element.register(None, element_name, Gst.Rank.NONE, request_element) is True
    )
    return request_element


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

    transform = define_subclass(
        GstBase.BaseTransform,
        type_name=type_name,
        attrs={
            "level": Property(default=7),
            "pinged": GObject.Signal(int),
            "do_start": do_start,
            "do_stop": do_stop,
            "do_transform_ip": do_transform_ip,
        },
        class_name="Transform",
    )
    transform.set_metadata(
        "Python Transform Property Signal", "Filter/Effect", "probe", "ginext"
    )
    transform.add_pad_template(
        Gst.PadTemplate.new(
            "sink", Gst.PadDirection.SINK, Gst.PadPresence.ALWAYS, _AUDIO_CAPS
        )
    )
    transform.add_pad_template(
        Gst.PadTemplate.new(
            "src", Gst.PadDirection.SRC, Gst.PadPresence.ALWAYS, _AUDIO_CAPS
        )
    )
    assert Gst.Element.register(None, element_name, Gst.Rank.NONE, transform) is True
    return transform
