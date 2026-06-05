# SPDX-License-Identifier: LGPL-2.1-or-later

"""Tests for request-pad element authoring."""

from __future__ import annotations

from .support import Gst, author_request_class, gst_bucket, unique


def test_request_pad_subclass_dispatches_request_and_release_vfuncs() -> None:
    state = {
        "request_new_pad": 0,
        "release_pad": 0,
    }
    element_name = unique("request_element").lower()
    author_request_class(
        type_name=unique("RequestType"),
        element_name=element_name,
        state=state,
    )

    elt = Gst.ElementFactory.make(element_name)
    pad = elt.request_pad("src_%u")
    try:
        assert pad.get_name().startswith("src_")
    finally:
        elt.release_request_pad(pad)

    assert state == {"request_new_pad": 1, "release_pad": 1}


def test_request_pad_subclass_registration_records_request_pad_template_metadata() -> (
    None
):
    state = {
        "request_new_pad": 0,
        "release_pad": 0,
    }
    element_name = unique("request_meta").lower()
    cls = author_request_class(
        type_name=unique("RequestMetaType"),
        element_name=element_name,
        state=state,
    )
    bucket = gst_bucket(cls)

    assert bucket["element_metadata"]["longname"] == "Python Request"
    assert [templ.name_template for templ in bucket["pad_templates"]] == [
        "sink",
        "src_%u",
    ]
    assert Gst.ElementFactory.find(element_name) is not None


def test_request_pad_allows_named_requests_and_multiple_pad_instances() -> None:
    state = {
        "request_new_pad": 0,
        "release_pad": 0,
    }
    element_name = unique("request_named").lower()
    author_request_class(
        type_name=unique("RequestNamedType"),
        element_name=element_name,
        state=state,
    )

    elt = Gst.ElementFactory.make(element_name)
    pad_a = elt.request_pad("src_%u", "src_7")
    pad_b = elt.request_pad("src_%u")
    try:
        assert pad_a.get_name() == "src_7"
        assert pad_b.get_name().startswith("src_")
        assert pad_a.get_name() != pad_b.get_name()
    finally:
        elt.release_request_pad(pad_a)
        elt.release_request_pad(pad_b)

    assert state["request_new_pad"] == 2
    assert state["release_pad"] == 2
