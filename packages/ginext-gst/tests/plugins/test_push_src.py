# SPDX-License-Identifier: LGPL-2.1-or-later

"""Tests for GstBase.PushSrc plugin authoring."""

from __future__ import annotations

import json
import pathlib
import pytest
import subprocess
import sys

from .support import (
    Gst,
    author_element_class,
    author_push_src_class,
    any_caps,
    gst_bucket,
    GstBase,
    unique,
)


def test_pushsrc_subclass_registration_records_source_metadata() -> None:
    """Registers a PushSrc subclass with authored source metadata and templates."""
    state = {"start": 0, "create": 0, "stop": 0}
    element_name = unique("push_src").lower()
    cls = author_push_src_class(
        type_name=unique("PushSrcType"),
        element_name=element_name,
        state=state,
    )

    bucket = gst_bucket(cls)
    assert bucket["element_metadata"]["longname"] == "Python Push Src"
    assert [templ.name_template for templ in bucket["pad_templates"]] == ["src"]
    assert Gst.ElementFactory.find(element_name) is not None


def test_pushsrc_dispatches_start_create_and_stop_vfuncs() -> None:
    """Runs a minimal pipeline and checks that PushSrc lifecycle vfuncs dispatch."""
    support_dir = pathlib.Path(__file__).resolve().parent
    code = f"""
import json
import os
import sys
import time

sys.path.insert(0, {str(support_dir)!r})
from support import Gst, author_push_src_class, unique

state = {{"start": 0, "create": 0, "stop": 0}}
element_name = unique("push_src_lifecycle").lower()
author_push_src_class(
    type_name=unique("PushSrcLifecycleType"),
    element_name=element_name,
    state=state,
)
pipe = Gst.parse_launch(f"{{element_name}} num-buffers=1 ! fakesink")
assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
bus = pipe.get_bus()
deadline = time.monotonic() + 2.0
while time.monotonic() < deadline:
    msg = bus.timed_pop_filtered(
        50 * Gst.MSECOND, Gst.MessageType.ERROR | Gst.MessageType.EOS
    )
    if msg is not None and msg.type == Gst.MessageType.ERROR:
        raise AssertionError(msg.parse_error())
    if state["start"] >= 1 and state["create"] >= 1:
        break
    time.sleep(0.01)
else:
    raise AssertionError(state)

print(json.dumps(state))
sys.stdout.flush()
os._exit(0)
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    state = json.loads(proc.stdout.strip())
    assert state["start"] >= 1
    assert state["create"] >= 1


def test_pushsrc_produces_data_in_a_minimal_pipeline() -> None:
    """Confirms a PushSrc subclass can drive a one-buffer pipeline to EOS."""
    support_dir = pathlib.Path(__file__).resolve().parent
    code = f"""
import json
import os
import sys
import time

sys.path.insert(0, {str(support_dir)!r})
from support import Gst, author_push_src_class, unique

state = {{"start": 0, "create": 0, "stop": 0}}
element_name = unique("push_src_pipeline").lower()
author_push_src_class(
    type_name=unique("PushSrcPipelineType"),
    element_name=element_name,
    state=state,
)
pipe = Gst.parse_launch(f"{{element_name}} num-buffers=1 ! fakesink")
assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
bus = pipe.get_bus()
deadline = time.monotonic() + 2.0
while time.monotonic() < deadline:
    msg = bus.timed_pop_filtered(
        50 * Gst.MSECOND, Gst.MessageType.ERROR | Gst.MessageType.EOS
    )
    if msg is not None and msg.type == Gst.MessageType.ERROR:
        raise AssertionError(msg.parse_error())
    if state["create"] >= 1:
        break
    time.sleep(0.01)
else:
    raise AssertionError(state)

print(json.dumps(state))
sys.stdout.flush()
os._exit(0)
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    state = json.loads(proc.stdout.strip())
    assert state["create"] >= 1


def test_ambiguous_do_alloc_on_pushsrc_requires_explicit_base_name() -> None:
    """Rejects the ambiguous short-form alloc override on PushSrc."""
    with pytest.raises(TypeError, match="do_alloc"):
        author_element_class(
            base_cls=GstBase.PushSrc,
            type_name=unique("PushSrcAllocType"),
            element_name=unique("push_src_alloc").lower(),
            methods={
                "do_start": lambda self: True,
                "do_stop": lambda self: True,
                "do_alloc": lambda self, offset, size: (
                    Gst.FlowReturn.OK,
                    Gst.Buffer.new_allocate(None, size, None),
                ),
                "do_fill": lambda self, offset, size, buf: Gst.FlowReturn.EOS,
            },
            metadata={
                "longname": "Python Push Src Alloc",
                "classification": "Source",
                "description": "probe",
                "author": "ginext",
            },
            pad_templates=[
                Gst.PadTemplate.new(
                    "src", Gst.PadDirection.SRC, Gst.PadPresence.ALWAYS, any_caps()
                )
            ],
        )


def test_explicit_do_base_src_alloc_receives_offset_and_size() -> None:
    """Binds the BaseSrc alloc vfunc explicitly and checks its argument shape."""
    seen: list[list[int]] = []
    element_name = unique("push_src_explicit_alloc").lower()

    def do_base_src_alloc(
        self: GstBase.PushSrc, offset: int, size: int
    ) -> tuple[Gst.FlowReturn, None]:
        seen.append([offset, size])
        return (Gst.FlowReturn.EOS, None)

    author_element_class(
        base_cls=GstBase.PushSrc,
        type_name=unique("PushSrcExplicitAllocType"),
        element_name=element_name,
        methods={
            "do_start": lambda self: True,
            "do_stop": lambda self: True,
            "do_base_src_alloc": do_base_src_alloc,
            "do_base_src_fill": lambda self, offset, size, buf: Gst.FlowReturn.EOS,
        },
        metadata={
            "longname": "Python Push Src Explicit Alloc",
            "classification": "Source",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=[
            Gst.PadTemplate.new(
                "src", Gst.PadDirection.SRC, Gst.PadPresence.ALWAYS, any_caps()
            )
        ],
    )

    support_dir = pathlib.Path(__file__).resolve().parent
    code = f"""
import json
import os
import sys
import time

sys.path.insert(0, {str(support_dir)!r})
from support import Gst, GstBase, any_caps, author_element_class, unique

seen = []
element_name = unique("push_src_explicit_alloc").lower()

author_element_class(
    base_cls=GstBase.PushSrc,
    type_name=unique("PushSrcExplicitAllocType"),
    element_name=element_name,
    methods={{
        "do_start": lambda self: True,
        "do_stop": lambda self: True,
        "do_base_src_alloc": lambda self, offset, size: (
            seen.append((offset, size)) or Gst.FlowReturn.EOS,
            None,
        ),
        "do_base_src_fill": lambda self, offset, size, buf: Gst.FlowReturn.EOS,
    }},
    metadata={{
        "longname": "Python Push Src Explicit Alloc",
        "classification": "Source",
        "description": "probe",
        "author": "ginext",
    }},
    pad_templates=[
        Gst.PadTemplate.new(
            "src", Gst.PadDirection.SRC, Gst.PadPresence.ALWAYS, any_caps()
        )
    ],
)

pipe = Gst.parse_launch(f"{{element_name}} num-buffers=1 ! fakesink")
assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
bus = pipe.get_bus()
deadline = time.monotonic() + 2.0
while time.monotonic() < deadline:
    msg = bus.timed_pop_filtered(
        50 * Gst.MSECOND, Gst.MessageType.ERROR | Gst.MessageType.EOS
    )
    if msg is not None and msg.type == Gst.MessageType.ERROR:
        raise AssertionError(msg.parse_error())
    if seen:
        break
    time.sleep(0.01)
else:
    raise AssertionError(seen)

print(json.dumps(seen))
sys.stdout.flush()
os._exit(0)
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    seen = json.loads(proc.stdout.strip())
    assert seen == [[0, 4096]]


def test_pushsrc_alloc_fill_authoring_can_be_registered() -> None:
    """Verifies alloc/fill-authored PushSrc subclasses register and surface the vfuncs."""
    cls = author_element_class(
        base_cls=GstBase.PushSrc,
        type_name=unique("PushSrcAllocMetaType"),
        element_name=unique("push_src_alloc_meta").lower(),
        methods={
            "do_start": lambda self: True,
            "do_stop": lambda self: True,
            "do_base_src_alloc": lambda self, offset, size: (
                Gst.FlowReturn.OK,
                Gst.Buffer.new_allocate(None, size, None),
            ),
            "do_base_src_fill": lambda self, offset, size, buf: Gst.FlowReturn.EOS,
        },
        metadata={
            "longname": "Python Push Src Alloc",
            "classification": "Source",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=[
            Gst.PadTemplate.new(
                "src", Gst.PadDirection.SRC, Gst.PadPresence.ALWAYS, any_caps()
            )
        ],
    )

    assert (
        Gst.ElementFactory.find(
            cls.gimeta.extensions["Gst"]["registrations"][-1]["name"]
        )
        is not None
    )
    assert "alloc" in GstBase.PushSrc.gimeta.vfunc_infos
    assert "fill" in GstBase.PushSrc.gimeta.vfunc_infos
