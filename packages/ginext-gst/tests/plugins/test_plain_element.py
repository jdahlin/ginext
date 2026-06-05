# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from ginext import Gst

from .support import Property, unique

if TYPE_CHECKING:
    from collections.abc import Callable


def _install_post_construct_hook(
    cls: type[Gst.Element], hook: Callable[[Gst.Element], None]
) -> None:
    core = cls.gimeta.extensions.setdefault("core", {})
    assert isinstance(core, dict)
    hooks = core.setdefault("post_construct_hooks", [])
    assert isinstance(hooks, list)
    hooks.append(hook)


def test_plain_element_pad_chain_event_query_authoring() -> None:
    state = {
        "chain": 0,
        "event": 0,
        "query": 0,
    }
    caps = Gst.Caps.from_string(
        "audio/x-raw,format=S16LE,rate=44100,channels=1,layout=interleaved"
    )

    class Plain(Gst.Element):
        sinkpad: Gst.Pad
        srcpad: Gst.Pad

    def _pad_setup(self: Gst.Element) -> None:
        assert isinstance(self, Plain)
        sink_template = self.get_pad_template("sink")
        src_template = self.get_pad_template("src")
        assert sink_template is not None
        assert src_template is not None
        self.sinkpad = Gst.Pad.new_from_template(sink_template, "sink")
        self.srcpad = Gst.Pad.new_from_template(src_template, "src")

        def chain(
            pad: Gst.Pad, parent: Gst.Object | None, buffer: Gst.Buffer
        ) -> Gst.FlowReturn:
            state["chain"] += 1
            return self.srcpad.push(buffer)

        def event(pad: Gst.Pad, parent: Gst.Object | None, event: Gst.Event) -> bool:
            state["event"] += 1
            return pad.event_default(parent, event)

        def query(pad: Gst.Pad, parent: Gst.Object | None, query: Gst.Query) -> bool:
            state["query"] += 1
            return pad.query_default(parent, query)

        self.sinkpad.set_chain_function_full(chain)
        self.sinkpad.set_event_function_full(event)
        self.srcpad.set_query_function_full(query)
        self.add_pad(self.sinkpad)
        self.add_pad(self.srcpad)

    _install_post_construct_hook(Plain, _pad_setup)

    element_name = unique("plain_pad_fns").lower()
    Plain.set_metadata("Plain", "Generic", "probe", "ginext")
    for name, direction in (
        ("sink", Gst.PadDirection.SINK),
        ("src", Gst.PadDirection.SRC),
    ):
        Plain.add_pad_template(
            Gst.PadTemplate.new(name, direction, Gst.PadPresence.ALWAYS, caps)
        )

    assert Gst.Element.register(None, element_name, Gst.Rank.NONE, Plain) is True

    pipe = Gst.parse_launch(
        "audiotestsrc num-buffers=1 ! "
        "audio/x-raw,format=S16LE,rate=44100,channels=1,layout=interleaved ! "
        f"{element_name} ! fakesink"
    )
    try:
        assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
        bus = pipe.get_bus()
        assert bus is not None
        msg = bus.timed_pop_filtered(
            5 * Gst.SECOND, Gst.MessageType.EOS | Gst.MessageType.ERROR
        )
        assert msg is not None
        assert msg.type != Gst.MessageType.ERROR
    finally:
        pipe.set_state(Gst.State.NULL)

    assert state["chain"] == 1


def test_plain_element_factory_make_runs_python_init_hook_for_pad_setup() -> None:
    caps = Gst.Caps.from_string("application/octet-stream")

    class Plain(Gst.Element):
        sinkpad: Gst.Pad
        srcpad: Gst.Pad

    def _pad_setup(self: Gst.Element) -> None:
        assert isinstance(self, Plain)
        sink_template = self.get_pad_template("sink")
        src_template = self.get_pad_template("src")
        assert sink_template is not None
        assert src_template is not None
        self.sinkpad = Gst.Pad.new_from_template(sink_template, "sink")
        self.srcpad = Gst.Pad.new_from_template(src_template, "src")
        self.add_pad(self.sinkpad)
        self.add_pad(self.srcpad)

    _install_post_construct_hook(Plain, _pad_setup)

    element_name = unique("plain_factory_pad_fns").lower()
    Plain.set_metadata("Plain", "Generic", "probe", "ginext")
    for name, direction in (
        ("sink", Gst.PadDirection.SINK),
        ("src", Gst.PadDirection.SRC),
    ):
        Plain.add_pad_template(
            Gst.PadTemplate.new(name, direction, Gst.PadPresence.ALWAYS, caps)
        )

    assert Gst.Element.register(None, element_name, Gst.Rank.NONE, Plain) is True

    elt = Gst.ElementFactory.make(element_name)
    assert elt.get_static_pad("sink") is not None
    assert elt.get_static_pad("src") is not None


def test_plain_element_parse_launch_runs_init_before_construct_properties() -> None:
    caps = Gst.Caps.from_string("application/octet-stream")
    seen_in_init: list[int] = []

    class Plain(Gst.Element):
        sinkpad: Gst.Pad
        srcpad: Gst.Pad
        number: int = Property(default=0)
        marker: str

        def __init__(self) -> None:
            super().__init__()
            seen_in_init.append(self.number)
            self.marker = "set-in-init"

    def _pad_setup(self: Gst.Element) -> None:
        assert isinstance(self, Plain)
        sink_template = self.get_pad_template("sink")
        src_template = self.get_pad_template("src")
        assert sink_template is not None
        assert src_template is not None
        self.sinkpad = Gst.Pad.new_from_template(sink_template, "sink")
        self.srcpad = Gst.Pad.new_from_template(src_template, "src")

        def chain(
            _pad: Gst.Pad, _parent: Gst.Object | None, buffer: Gst.Buffer
        ) -> Gst.FlowReturn:
            return self.srcpad.push(buffer)

        self.sinkpad.set_chain_function_full(chain)
        self.add_pad(self.sinkpad)
        self.add_pad(self.srcpad)

    _install_post_construct_hook(Plain, _pad_setup)

    element_name = unique("plain_launch_prop").lower()
    Plain.set_metadata("Plain", "Generic", "probe", "ginext")
    for name, direction in (
        ("sink", Gst.PadDirection.SINK),
        ("src", Gst.PadDirection.SRC),
    ):
        Plain.add_pad_template(
            Gst.PadTemplate.new(name, direction, Gst.PadPresence.ALWAYS, caps)
        )

    assert Gst.Element.register(None, element_name, Gst.Rank.NONE, Plain) is True

    pipe = Gst.parse_launch(
        f"fakesrc num-buffers=1 ! {element_name} name=probe number=42 ! fakesink"
    )
    elt: Plain | None = None
    try:
        maybe_elt = pipe.get_by_name("probe")
        assert isinstance(maybe_elt, Plain)
        elt = maybe_elt
        assert elt is not None
        assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
        bus = pipe.get_bus()
        assert bus is not None
        msg = bus.timed_pop_filtered(
            5 * Gst.SECOND, Gst.MessageType.EOS | Gst.MessageType.ERROR
        )
        assert msg is not None
        assert msg.type != Gst.MessageType.ERROR
        assert seen_in_init == [0]
        assert elt.marker == "set-in-init"
        assert elt.number == 42
        assert elt.get_static_pad("sink") is not None
        assert elt.get_static_pad("src") is not None
    finally:
        pipe.set_state(Gst.State.NULL)
        if elt is not None:
            pipe.remove(elt)
