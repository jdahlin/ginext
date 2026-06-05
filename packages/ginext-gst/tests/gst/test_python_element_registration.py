# SPDX-License-Identifier: LGPL-2.1-or-later

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

from __future__ import annotations

import itertools
from typing import Any

from ginext import Gst, GstBase

Gst.init(None)

_counter = itertools.count()
_CAPS = Gst.Caps.from_string(
    "audio/x-raw,format=S16LE,rate=44100,channels=1,layout=interleaved"
)


def _unique(name: str) -> str:
    return f"Ginext{name}_{next(_counter)}"


def _build_transform() -> type[Any]:
    class AuthoringTransform(GstBase.BaseTransform):
        def do_transform_ip(self, buf: Gst.Buffer) -> Gst.FlowReturn:
            return Gst.FlowReturn.OK

    return AuthoringTransform


def test_python_element_registration_tracks_authoring_state_on_gimeta() -> None:
    cls = _build_transform()

    assert "Gst" not in cls.gimeta.extensions

    cls.set_metadata("Authoring Probe", "Filter/Effect", "probe", "ginext")
    cls.add_pad_template(
        Gst.PadTemplate.new(
            "sink", Gst.PadDirection.SINK, Gst.PadPresence.ALWAYS, _CAPS
        )
    )
    cls.add_pad_template(
        Gst.PadTemplate.new("src", Gst.PadDirection.SRC, Gst.PadPresence.ALWAYS, _CAPS)
    )

    bucket = cls.gimeta.extensions["Gst"]
    assert bucket == {
        "element_metadata": {
            "longname": "Authoring Probe",
            "classification": "Filter/Effect",
            "description": "probe",
            "author": "ginext",
        },
        "pad_templates": bucket["pad_templates"],
        "registrations": [],
    }
    assert bucket["element_metadata"] == {
        "longname": "Authoring Probe",
        "classification": "Filter/Effect",
        "description": "probe",
        "author": "ginext",
    }
    assert [templ.name_template for templ in bucket["pad_templates"]] == ["sink", "src"]


def test_python_element_registration_records_factory_registration_on_gimeta() -> None:
    cls = _build_transform()
    element_name = _unique("authoring_transform")

    cls.set_metadata("Authoring Probe", "Filter/Effect", "probe", "ginext")
    cls.add_pad_template(
        Gst.PadTemplate.new(
            "sink", Gst.PadDirection.SINK, Gst.PadPresence.ALWAYS, _CAPS
        )
    )
    cls.add_pad_template(
        Gst.PadTemplate.new("src", Gst.PadDirection.SRC, Gst.PadPresence.ALWAYS, _CAPS)
    )

    assert Gst.Element.register(None, element_name, Gst.Rank.NONE, cls) is True

    bucket = cls.gimeta.extensions["Gst"]
    assert bucket["element_metadata"] == {
        "longname": "Authoring Probe",
        "classification": "Filter/Effect",
        "description": "probe",
        "author": "ginext",
    }
    assert [templ.name_template for templ in bucket["pad_templates"]] == ["sink", "src"]
    assert bucket["registrations"] == [
        {
            "plugin": None,
            "name": element_name,
            "rank": Gst.Rank.NONE,
        }
    ]

    factory = Gst.ElementFactory.find(element_name)
    assert factory is not None
    assert factory.get_longname() == "Authoring Probe"
