# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import json
import pathlib
import subprocess
import sys


from .support import author_transform_with_property_signal_class, unique


def test_transform_element_properties_have_defaults_and_are_mutable() -> None:
    state = {
        "start": 0,
        "stop": 0,
    }
    element_name = unique("property_signal_transform")
    cls = author_transform_with_property_signal_class(
        type_name=unique("PropertySignalType"),
        element_name=element_name,
        state=state,
    )

    elt = cls()
    assert elt.level == 7
    elt.level = 11
    assert elt.level == 11


def test_transform_element_signal_and_start_stop_hooks_run_in_pipeline() -> None:
    support_dir = pathlib.Path(__file__).resolve().parent
    code = f"""
import json
import os
import sys
import time

sys.path.insert(0, {str(support_dir)!r})
from support import author_transform_with_property_signal_class, unique
from ginext import Gst

state = {{
    "start": 0,
    "stop": 0,
}}
seen = []
element_name = unique("property_signal_pipeline")
author_transform_with_property_signal_class(
    type_name=unique("PropertySignalPipelineType"),
    element_name=element_name,
    state=state,
)

pipe = Gst.parse_launch(
    "audiotestsrc num-buffers=1 ! "
    "audio/x-raw,format=S16LE,rate=44100,channels=1,layout=interleaved ! "
    f"{{element_name}} name=f ! fakesink"
)
elt = pipe.get_by_name("f")
elt.level = 13
elt.pinged.connect(lambda _src, value: seen.append(value), owner=elt)
assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
bus = pipe.get_bus()
deadline = time.monotonic() + 2.0
while time.monotonic() < deadline:
    msg = bus.timed_pop_filtered(
        50 * Gst.MSECOND, Gst.MessageType.ERROR | Gst.MessageType.EOS
    )
    if msg is not None and msg.type == Gst.MessageType.ERROR:
        raise AssertionError(msg.parse_error())
    if seen == [13] and state["start"] >= 1:
        break
    time.sleep(0.01)
else:
    raise AssertionError({{"seen": seen, "state": state}})

print(json.dumps({{"seen": seen, "state": state}}))
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
    payload = json.loads(proc.stdout.strip())
    assert payload["seen"] == [13]
    assert payload["state"]["start"] == 1
