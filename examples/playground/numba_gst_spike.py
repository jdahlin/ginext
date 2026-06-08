"""Spike: can a GStreamer filter element be written in ginext such that its
hot inner loop is a JIT-compilable kernel, while the GObject shell stays
interpreted?

Architecture under test
-----------------------
    do_transform_ip   (interpreted, ~once per buffer)
        map buffer -> numpy array view
        call kernel(samples, gain)        <-- the only hot code
        unmap / write back
        return Gst.FlowReturn.OK

The kernel touches ZERO GObject machinery -- it is pure arithmetic over a
flat array, which is exactly what numba's @njit compiles well. We therefore
want to JIT *only* the kernel, not the vfunc.

environment caveats (as of 2026-05-30, this checkout)
-----------------------------------------------------
1. numba has no wheel for CPython 3.14 free-threaded (this interpreter), and
   numpy is not installed in .venv, so we cannot actually @njit here. `jit`
   below uses numba if importable and otherwise is a no-op decorator -- the
   kernel is plain numpy either way. The point of the spike is the *boundary*,
   which is identical whether or not the kernel is compiled: numba would simply
   replace the function body's machine code.
2. info.data is currently *immutable bytes* (a copy made by the Gst.py:106
   overlay via extract_dup), NOT a writable view. So write-back today must go
   through buf.fill(). A zero-copy writable mapping is the binding change
   that turns this from "fast kernel + 2 copies" into true zero-copy vroom.

VERIFIED on this checkout (Gst 1.28.3): the pipeline
    audiotestsrc num-buffers=3
      ! audio/x-raw,format=S16LE,rate=44100,channels=1
      ! <this element> ! fakesink
runs to EOS with do_transform_ip called 3x over 8192 bytes, and the in-place
READ|WRITE map succeeds on the upstream buffers. ginext DOES dispatch GI
base-class vfuncs (transform_ip is in Gain.gimeta.vfunc_infos).

Gotchas found:
  - set_metadata(...) + add_pad_template(Gst.PadTemplate.new(name, dir,
    Gst.PadPresence.ALWAYS, caps)) for both "sink" and "src" are required
    before Gst.Element.register(...).
  - Pad-template caps must be specific enough to negotiate (full
    audio/x-raw,...), not bare application/x-raw, or linking fails.
  - appsrc/appsink action signals are NOT in signal_infos: use the GstApp
    methods src.push_buffer(buf) / src.end_of_stream() / sink.pull_sample().
  - Gst.Buffer.new_wrapped(bytes) is non-writable; only upstream-produced
    buffers can be WRITE-mapped.
"""

from __future__ import annotations

import array
from collections.abc import Callable
from typing import Any, cast

from ginext import defaults

defaults.require("Gst", "1.0")
defaults.require("GstBase", "1.0")

from ginext import Gst, GstBase
import numpy as np

HAVE_NUMPY = True

try:
    from numba import njit as _njit

    def jit(f: Callable[..., Any]) -> Callable[..., Any]:
        return cast("Callable[..., Any]", _njit(cache=True)(f))

    JIT_BACKEND = "numba"
except ImportError:

    def jit(f: Callable[..., Any]) -> Callable[..., Any]:
        return f

    JIT_BACKEND = "numpy" if HAVE_NUMPY else "pure-python fallback"


# --- the hot kernel: pure arithmetic, no GObject anything -------------------
# This is the ONLY code that should ever be JIT-compiled. It runs once per
# sample (millions/sec) and touches zero GObject machinery -- just an array.
# With numba installed this @jit becomes LLVM machine code; the boundary
# (flat numeric buffer in, mutated in place) is identical either way.
@jit
def apply_gain(samples: Any, gain: float) -> Any:
    for i in range(len(samples)):
        v = int(samples[i] * gain)
        samples[i] = -32768 if v < -32768 else 32767 if v > 32767 else v
    return samples


Gst.init(None)


class GainTransform(GstBase.BaseTransform, type_name="GinextSpikeGain"):

    gain = 2.0
    calls = 0  # class-level counters so main() can read them after EOS
    samples = 0
    writable = 0

    # The ONE function. Called once per buffer on the streaming thread.
    # Returns a GstFlowReturn -- that is how it "signals it is done".
    def do_transform_ip(self, buf: Gst.Buffer) -> Gst.FlowReturn:
        cls = type(self)
        cls.calls += 1
        # Try a writable map; on this checkout audiotestsrc buffers are NOT
        # writable, so fall back to a READ map and compute on a copy. (For real
        # in-place processing you need a writable upstream buffer.)
        ok, info = buf.map(Gst.MapFlags.READ | Gst.MapFlags.WRITE)
        writable = ok
        if not ok:
            ok, info = buf.map(Gst.MapFlags.READ)
        if not ok:
            return Gst.FlowReturn.ERROR
        try:
            cls.samples += info.size
            cls.writable += int(writable)
            # info.data is immutable bytes (a copy from the Gst.py:106
            # extract_dup overlay), so we load a mutable array, run the kernel,
            # and -- only if the buffer is writable -- write it back. A writable
            # zero-copy map *view* would eliminate both copies; that plus a
            # writable upstream buffer is what true in-place vroom needs.
            arr: Any
            if HAVE_NUMPY:
                arr = np.frombuffer(info.data, dtype=np.int16).copy()
            else:
                arr = array.array("h")
                arr.frombytes(info.data[: (info.size // 2) * 2])
            apply_gain(arr, self.gain)
            if writable:
                buf.fill(0, arr.tobytes())
        finally:
            buf.unmap(info)
        return Gst.FlowReturn.OK


CAPS_STRING = "audio/x-raw,format=S16LE,rate=44100,channels=1,layout=interleaved"


def main() -> None:
    print(f"[spike] JIT backend: {JIT_BACKEND}")

    # Warm up the JIT kernel BEFORE the pipeline plays. numba compiles on first
    # call (~1-2s); if that happens inside do_transform_ip on the streaming
    # thread it stalls the pipeline (observed: only 1 buffer made it through and
    # the bus wait timed out). Compiling here, off the streaming thread, fixes
    # it -- the streaming-thread calls then hit cached machine code.
    if JIT_BACKEND == "numba":
        warm = np.zeros(8, dtype=np.int16)
        apply_gain(warm, 2.0)
        print("[spike] kernel warmed (compiled off the streaming thread)")

    # Metadata + pad templates are required before register() succeeds, and the
    # caps must be specific enough to negotiate (not bare application/x-raw).
    caps = Gst.Caps.from_string(CAPS_STRING)
    GainTransform.set_metadata("Spike Gain", "Filter/Effect", "spike", "you")
    for nm, d in (("sink", Gst.PadDirection.SINK), ("src", Gst.PadDirection.SRC)):
        GainTransform.add_pad_template(
            Gst.PadTemplate.new(nm, d, Gst.PadPresence.ALWAYS, caps)
        )
    ok = Gst.Element.register(None, "ginext_spike_gain", Gst.Rank.NONE, GainTransform)
    print(f"[spike] element registered: {ok}")

    # audiotestsrc produces WRITABLE upstream buffers (unlike new_wrapped), so
    # the in-place READ|WRITE map in do_transform_ip works.
    pipe = Gst.parse_launch(
        f"audiotestsrc num-buffers=3 ! {CAPS_STRING} ! ginext_spike_gain ! fakesink"
    )
    pipe.set_state(Gst.State.PLAYING)
    bus = pipe.get_bus()
    assert bus is not None
    # 15s cap: generous enough to cover JIT compile if warmup were skipped,
    # but bounded so a stalled pipeline can't hang the spike indefinitely.
    msg = bus.timed_pop_filtered(
        15 * Gst.SECOND, Gst.MessageType.EOS | Gst.MessageType.ERROR
    )
    if msg is not None and msg.type == Gst.MessageType.ERROR:
        err, _dbg = msg.parse_error()
        print(f"[spike] pipeline error: {err.message}")
    else:
        print(f"[spike] reached: {msg.type if msg else 'timeout'}")
    print(
        f"[spike] do_transform_ip calls: {GainTransform.calls}  "
        f"bytes: {GainTransform.samples}  "
        f"writable_maps: {GainTransform.writable}"
    )
    pipe.set_state(Gst.State.NULL)


if __name__ == "__main__":
    main()
    # NOTE: on this mid-refactor checkout the process SEGFAULTs during normal
    # interpreter shutdown (GStreamer + free-threaded teardown ordering), AFTER
    # all results above are correct. Skip the crashy finalizers for a clean
    # exit; drop this os._exit once shutdown is stable.
    import os

    os._exit(0)
