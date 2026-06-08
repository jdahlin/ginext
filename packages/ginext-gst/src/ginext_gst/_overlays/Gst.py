# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, see <http://www.gnu.org/licenses/>.

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

from __future__ import annotations

import enum
import itertools
from typing import Any, TYPE_CHECKING, Protocol, SupportsInt, runtime_checkable

from ginext import Gst, GLib, GObject
from ginext.gobject.gobjectclass import GObject as _GObject

if TYPE_CHECKING:
    from collections.abc import Iterator
    from ginext.overlay.registrar import OverlayRegistrar

overlay: OverlayRegistrar = Gst.overlay


@runtime_checkable
class _FractionLike(Protocol):
    num: SupportsInt
    denom: SupportsInt


@runtime_checkable
class _BitmaskLike(Protocol):
    v: int


@runtime_checkable
class _RangeLike(Protocol):
    range: range


def apply_to_namespace(namespace: Any) -> None:
    if hasattr(namespace, "ElementFactoryListType"):
        return

    class ElementFactoryListType(enum.IntFlag):
        ANY = int(namespace.ELEMENT_FACTORY_TYPE_ANY)
        SRC = int(namespace.ELEMENT_FACTORY_TYPE_SRC)
        SINK = int(namespace.ELEMENT_FACTORY_TYPE_SINK)
        MEDIA_AUDIO = int(namespace.ELEMENT_FACTORY_TYPE_MEDIA_AUDIO)
        MEDIA_VIDEO = int(namespace.ELEMENT_FACTORY_TYPE_MEDIA_VIDEO)
        MEDIA_IMAGE = int(namespace.ELEMENT_FACTORY_TYPE_MEDIA_IMAGE)
        MEDIA_SUBTITLE = int(namespace.ELEMENT_FACTORY_TYPE_MEDIA_SUBTITLE)
        MEDIA_METADATA = int(namespace.ELEMENT_FACTORY_TYPE_MEDIA_METADATA)
        MEDIA_ANY = int(namespace.ELEMENT_FACTORY_TYPE_MEDIA_ANY)
        DECODER = int(namespace.ELEMENT_FACTORY_TYPE_DECODER)
        ENCODER = int(namespace.ELEMENT_FACTORY_TYPE_ENCODER)
        SINKS = int(namespace.ELEMENT_FACTORY_TYPE_SINK)
        MUXER = int(namespace.ELEMENT_FACTORY_TYPE_MUXER)
        DEMUXER = int(namespace.ELEMENT_FACTORY_TYPE_DEMUXER)
        PARSER = int(namespace.ELEMENT_FACTORY_TYPE_PARSER)
        PAYLOADER = int(namespace.ELEMENT_FACTORY_TYPE_PAYLOADER)
        DEPAYLOADER = int(namespace.ELEMENT_FACTORY_TYPE_DEPAYLOADER)
        FORMATTER = int(namespace.ELEMENT_FACTORY_TYPE_FORMATTER)
        DECRYPTOR = int(namespace.ELEMENT_FACTORY_TYPE_DECRYPTOR)
        ENCRYPTOR = int(namespace.ELEMENT_FACTORY_TYPE_ENCRYPTOR)
        HARDWARE = int(namespace.ELEMENT_FACTORY_TYPE_HARDWARE)
        AUDIO_ENCODER = int(namespace.ELEMENT_FACTORY_TYPE_AUDIO_ENCODER)
        VIDEO_ENCODER = int(namespace.ELEMENT_FACTORY_TYPE_VIDEO_ENCODER)
        AUDIOVIDEO_SINKS = int(namespace.ELEMENT_FACTORY_TYPE_AUDIOVIDEO_SINKS)
        DECODABLE = int(namespace.ELEMENT_FACTORY_TYPE_DECODABLE)
        TIMESTAMPER = int(namespace.ELEMENT_FACTORY_TYPE_TIMESTAMPER)
        MAX_ELEMENTS = int(namespace.ELEMENT_FACTORY_TYPE_MAX_ELEMENTS)

    namespace.__dict__["ElementFactoryListType"] = ElementFactoryListType
    namespace.__dict__["ElementFactoryType"] = ElementFactoryListType


def _gimeta_extension_bucket(owner: Any, namespace: str) -> dict[str, Any] | None:
    try:
        gimeta = owner.gimeta
    except AttributeError:
        return None
    try:
        extensions = gimeta.extensions
    except AttributeError:
        return None
    if not isinstance(extensions, dict):
        return None
    bucket = extensions.get(namespace)
    if not isinstance(bucket, dict):
        bucket = {}
        extensions[namespace] = bucket
    return bucket


def _gst_extension_state(owner: Any) -> dict[str, Any] | None:
    bucket = _gimeta_extension_bucket(owner, "Gst")
    if bucket is None:
        return None
    metadata = bucket.get("element_metadata")
    if metadata is None or not isinstance(metadata, dict):
        bucket["element_metadata"] = {}
    pad_templates = bucket.get("pad_templates")
    if pad_templates is None or not isinstance(pad_templates, list):
        bucket["pad_templates"] = []
    registrations = bucket.get("registrations")
    if registrations is None or not isinstance(registrations, list):
        bucket["registrations"] = []
    return bucket


def _bind_typelib_descriptor(owner: type[Any], fn: Any) -> Any:
    try:
        getter = fn.__get__
    except AttributeError:
        return fn
    return getter(None, owner)


# ---------------------------------------------------------------------------
# GValue fallback for GStreamer custom-fundamental GTypes
# ---------------------------------------------------------------------------
# GstFraction, GstBitmask, GstValueArray, GstValueList, GstIntRange,
# GstInt64Range, GstDoubleRange, GstFractionRange are custom fundamental GTypes
# registered by GStreamer. They are not G_TYPE_BOXED or G_TYPE_OBJECT, so
# ginext's core GValue converter can't handle them. Rather than reach into
# GStreamer's (non-introspectable) C accessors, we lean on its own serializer:
# `Gst.value_serialize` renders the value to canonical text ("1/2", "[ 0, 100 ]",
# "< (int)1, (int)2 >", ...) and we parse that back into the introspected Gst
# value classes. Core stays generic — it only hands us the GValue via the
# type-agnostic `gvalue_wrap_pointer`; all GStreamer knowledge lives here.


def _parse_fraction(text: str) -> Any:
    num, _, denom = text.partition("/")
    return Gst.Fraction(int(num), int(denom) if denom else 1)


def _split_top_level(inner: str) -> list[str]:
    # Split a comma-separated gst container body, ignoring commas nested inside
    # <...>, {...} or [...].
    items: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(inner):
        if char in "<{[":
            depth += 1
        elif char in ">}]":
            depth -= 1
        elif char == "," and depth == 0:
            items.append(inner[start:index].strip())
            start = index + 1
    tail = inner[start:].strip()
    if tail:
        items.append(tail)
    return items


def _unwrap(text: str, open_char: str, close_char: str) -> str:
    text = text.strip()
    if text[:1] == open_char and text[-1:] == close_char:
        return text[1:-1].strip()
    return text


def _parse_string(text: str) -> str:
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return text


_ELEMENT_PARSERS: dict[str, Any] = {
    "int": int,
    "uint": int,
    "int64": int,
    "uint64": int,
    "long": int,
    "ulong": int,
    "double": float,
    "float": float,
    "boolean": lambda value: value.strip().lower() == "true",
    "string": _parse_string,
    "fraction": _parse_fraction,
}


def _parse_element(text: str) -> Any:
    # An array/list element serialized as "(type)value".
    text = text.strip()
    if text.startswith("("):
        close = text.index(")")
        type_tag = text[1:close]
        value = text[close + 1 :].strip()
    else:
        type_tag, value = "", text
    parser = _ELEMENT_PARSERS.get(type_tag)
    return parser(value) if parser is not None else value


def _range_parts(text: str) -> list[str]:
    return _split_top_level(_unwrap(text, "[", "]"))


def _build_value_array(text: str) -> Any:
    return Gst.ValueArray(
        [_parse_element(item) for item in _split_top_level(_unwrap(text, "<", ">"))]
    )


def _build_value_list(text: str) -> Any:
    return Gst.ValueList(
        [_parse_element(item) for item in _split_top_level(_unwrap(text, "{", "}"))]
    )


def _build_fraction_range(text: str) -> Any:
    low, high = _range_parts(text)
    return Gst.FractionRange(_parse_fraction(low), _parse_fraction(high))


_VALUE_BUILDERS: dict[str, Any] = {
    "GstFraction": _parse_fraction,
    "GstBitmask": lambda text: Gst.Bitmask(int(text, 16)),
    "GstIntRange": lambda text: Gst.IntRange(range(*(int(n) for n in _range_parts(text)))),
    "GstInt64Range": lambda text: Gst.Int64Range(
        range(*(int(n) for n in _range_parts(text)))
    ),
    "GstDoubleRange": lambda text: Gst.DoubleRange(*(float(n) for n in _range_parts(text))),
    "GstFractionRange": _build_fraction_range,
    "GstValueArray": _build_value_array,
    "GstValueList": _build_value_list,
}


def _install_gvalue_fallback() -> None:
    from ginext import private as _private

    serialize = Gst.value_serialize
    wrap_pointer = _private.gvalue_wrap_pointer
    type_name = GObject.type_name
    set_int = _private.gvalue_set_data_int
    set_uint64 = _private.gvalue_set_data_uint64

    def _to_py(gtype: int, ptr: int) -> Any:
        builder = _VALUE_BUILDERS.get(type_name(gtype))
        if builder is None:
            raise NotImplementedError(
                f"GValue return conversion: unsupported GStreamer GType {gtype}"
            )
        text = serialize(wrap_pointer(ptr))
        if text is None:
            raise NotImplementedError(
                f"GValue return conversion: could not serialize GStreamer GType {gtype}"
            )
        return builder(text)

    def _from_py(obj: Any, gtype: int, ptr: int) -> None:
        # The reverse direction: fill an initialised GstValue GValue in place.
        # GstFraction stores numerator/denominator in data[0]/data[1].v_int and
        # GstBitmask the mask in data[0].v_uint64 (mirroring gst_value_set_*); the
        # containers and the packed ranges still need GStreamer's own setter and
        # are left to the core caller-allocates-GValue path (a follow-up).
        name = type_name(gtype)
        if name == "GstFraction":
            set_int(ptr, 0, int(obj.num))
            set_int(ptr, 1, int(obj.denom))
            return
        if name == "GstBitmask":
            set_uint64(ptr, 0, int(obj.v))
            return
        raise NotImplementedError(
            f"GValue from Python: writing {name} is not supported yet"
        )

    _private.register_converter(_to_py, _from_py)


overlay.on_first_access(_install_gvalue_fallback)


# ---------------------------------------------------------------------------
# Exception classes
# ---------------------------------------------------------------------------


class NotInitialized(Exception):
    pass


class IteratorError(Exception):
    pass


class MissingPluginError(Exception):
    pass


class AddError(Exception):
    pass


class LinkError(Exception):
    pass


class MapError(Exception):
    pass


overlay.constant("NotInitialized", NotInitialized)
overlay.constant("IteratorError", IteratorError)
overlay.constant("MissingPluginError", MissingPluginError)
overlay.constant("AddError", AddError)
overlay.constant("LinkError", LinkError)
overlay.constant("MapError", MapError)


# ---------------------------------------------------------------------------
# Float GType wrapper
# ---------------------------------------------------------------------------


class Float(float):
    """Wraps a Python float as G_TYPE_FLOAT rather than G_TYPE_DOUBLE."""


overlay.constant("Float", Float)


# ---------------------------------------------------------------------------
# Iterator
# ---------------------------------------------------------------------------


@overlay.method("Iterator", name="__iter__")
def _iterator_iter(self: Any) -> Iterator[Any]:
    while True:
        result, value = self.next()
        if result == Gst.IteratorResult.DONE:
            break
        if result != Gst.IteratorResult.OK:
            raise IteratorError(result)
        yield value


# ---------------------------------------------------------------------------
# Buffer
# ---------------------------------------------------------------------------


@overlay.method("Buffer", name="map")
def _buffer_map(fn: Any, self: Any, flags: Any) -> tuple[bool, Any]:
    success, info = fn(self, flags)
    if success:
        info.__dict__["data"] = self.extract_dup(0, info.size)
    return success, info


# ---------------------------------------------------------------------------
# Element
# ---------------------------------------------------------------------------


@overlay.method("Element", as_staticmethod=True)
def link_many(*args: Any) -> None:
    for a, b in itertools.pairwise(args):
        if not a.link(b):
            raise LinkError(f"Failed to link {a} and {b}")


@overlay.method("Element", name="set_metadata", as_classmethod=True)
def _element_set_metadata(
    fn: Any,
    cls: type[Any],
    longname: str,
    classification: str,
    description: str,
    author: str,
) -> None:
    bucket = _gst_extension_state(cls)
    if bucket is not None:
        bucket["element_metadata"] = {
            "longname": longname,
            "classification": classification,
            "description": description,
            "author": author,
        }
    _bind_typelib_descriptor(cls, fn)(longname, classification, description, author)


@overlay.method("Element", name="add_pad_template", as_classmethod=True)
def _element_add_pad_template(fn: Any, cls: type[Any], templ: Any) -> None:
    bucket = _gst_extension_state(cls)
    if bucket is not None:
        bucket["pad_templates"].append(templ)
    _bind_typelib_descriptor(cls, fn)(templ)


@overlay.method("Element", name="register", as_staticmethod=True)
def _element_register(
    fn: Any,
    plugin: Any,
    name: str,
    rank: Any,
    type_: type[Any],
) -> Any:
    bucket = _gst_extension_state(type_)
    if bucket is not None:
        bucket["registrations"].append(
            {
                "plugin": plugin,
                "name": name,
                "rank": rank,
            }
        )
    return _bind_typelib_descriptor(type_, fn)(plugin, name, rank, type_)


@overlay.method("Element")
def request_pad(
    fn: Any, self: Any, templ: Any, name: str | None = None, caps: Any = None
) -> Any:
    if isinstance(templ, str):
        resolved = self.get_pad_template(templ)
        if resolved is None:
            raise KeyError(f"pad template {templ!r} not found")
        templ = resolved
    elif isinstance(templ, Gst.StaticPadTemplate):
        resolved = self.get_pad_template(templ.name_template)
        if resolved is None:
            raise KeyError(f"pad template {templ.name_template!r} not found")
        templ = resolved
    return fn(self, templ, name, caps)


# ---------------------------------------------------------------------------
# Bin
# ---------------------------------------------------------------------------


@overlay.method("Bin", name="__init__")
def _bin_init(self: Any, name: str | None = None) -> None:
    if name is not None:
        _GObject.__init__(self, name=name)
    else:
        _GObject.__init__(self)


@overlay.method("Bin", name="add")
def _bin_add(fn: Any, self: Any, *args: Any) -> None:
    for elem in args:
        if not fn(self, elem):
            raise AddError(elem)


@overlay.method("Bin", name="make_and_add")
def _bin_make_and_add(self: Any, factoryname: str, name: str | None = None) -> Any:
    elem = Gst.ElementFactory.make(factoryname, name)
    self.add(elem)
    return elem


@overlay.method("Bin", name="__iter__")
def _bin_iter(self: Any) -> Iterator[Any]:
    for elem in self.iterate_elements():
        yield elem


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


@overlay.method("Pipeline", name="__init__")
def _pipeline_init(self: Any, name: str | None = None) -> None:
    if name is not None:
        _GObject.__init__(self, name=name)
    else:
        _GObject.__init__(self)


# ---------------------------------------------------------------------------
# GhostPad
# ---------------------------------------------------------------------------


@overlay.method("GhostPad", name="__init__")
def _ghost_pad_init(
    self: Any,
    name: str,
    target: Any = None,
    direction: Any = None,
) -> None:
    if direction is None:
        if target is None:
            raise TypeError("you must pass at least one of target and direction")
        direction = target.get_property("direction")
    _GObject.__init__(self, name=name, direction=direction)
    self.construct()
    if target is not None:
        self.set_target(target)


# ---------------------------------------------------------------------------
# ElementFactory
# ---------------------------------------------------------------------------


@overlay.method("ElementFactory", name="get_longname")
def _element_factory_get_longname(self: Any) -> str | None:
    metadata = self.get_metadata("long-name")
    return None if metadata is None else str(metadata)


@overlay.method("ElementFactory", name="get_description")
def _element_factory_get_description(self: Any) -> str | None:
    metadata = self.get_metadata("description")
    return None if metadata is None else str(metadata)


@overlay.method("ElementFactory", name="get_klass")
def _element_factory_get_klass(self: Any) -> str | None:
    metadata = self.get_metadata("klass")
    return None if metadata is None else str(metadata)


@overlay.method("ElementFactory", name="make", as_staticmethod=True)
def _element_factory_make(fn: Any, factoryname: str, name: str | None = None) -> Any:
    elem = fn(factoryname, name)
    if not elem:
        raise MissingPluginError(f"No such element: {factoryname}")
    return elem


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------


@overlay.method("Structure", name="__new__", as_staticmethod=True)
def _structure_new(cls: type, arg: str | Any, **kwargs: Any) -> Any:
    if isinstance(arg, str):
        if not kwargs:
            return Gst.Structure.from_string(arg)[0]
        struct = Gst.Structure.new_empty(arg)
        for k, v in kwargs.items():
            struct.set_value(k, v)
        return struct
    elif isinstance(arg, Gst.Structure):
        return arg.copy()
    raise TypeError("wrong arguments when creating GstStructure object")


@overlay.method("Structure", name="__getitem__")
def _structure_getitem(self: Any, key: str) -> Any:
    val = self.get_value(key)
    if val is None:
        raise KeyError(f"key {key} not found")
    return val


@overlay.method("Structure", name="__setitem__")
def _structure_setitem(self: Any, key: str, value: Any) -> None:
    self.set_value(key, value)


@overlay.method("Structure", name="__len__")
def _structure_len(self: Any) -> int:
    return int(self.n_fields())


@overlay.method("Structure", name="__iter__")
def _structure_iter(self: Any) -> Iterator[str]:
    return _structure_keys(self)


@overlay.method("Structure", name="__str__")
def _structure_str(self: Any) -> str:
    return str(self.to_string())


@overlay.method("Structure", name="__repr__")
def _structure_repr(self: Any) -> str:
    return f"<Gst.Structure {self}>"


@overlay.method("Structure", name="items")
def _structure_items(self: Any) -> Iterator[tuple[str, Any]]:
    pairs: list[tuple[str, Any]] = []

    def foreach(fid: int, value: Any) -> bool:
        pairs.append((GLib.quark_to_string(fid), value))
        return True

    self.foreach(foreach)
    return iter(pairs)


@overlay.method("Structure", name="keys")
def _structure_keys(self: Any) -> Iterator[str]:
    key_list: list[str] = []

    def foreach(fid: int, value: Any) -> bool:
        key_list.append(GLib.quark_to_string(fid))
        return True

    self.foreach(foreach)
    return iter(key_list)


# ---------------------------------------------------------------------------
# Caps
# ---------------------------------------------------------------------------


@overlay.method("Caps", name="__new__", as_staticmethod=True)
def _caps_new(
    cls: type,
    arg: str | Any | list[Any] | tuple[Any, ...] | None = None,
) -> Any:
    if arg is None:
        return Gst.Caps.new_empty()
    elif isinstance(arg, str):
        return Gst.Caps.from_string(arg)
    elif isinstance(arg, Gst.Caps):
        return arg.copy()
    elif isinstance(arg, Gst.Structure):
        res = Gst.Caps.new_empty()
        res.append_structure(arg.copy())
        return res
    elif isinstance(arg, (list, tuple)):
        res = Gst.Caps.new_empty()
        for s in arg:
            res.append_structure(s.copy())
        return res
    raise TypeError("wrong arguments when creating GstCaps object")


@overlay.method("Caps", name="__str__")
def _caps_str(self: Any) -> str:
    return str(self.to_string())


@overlay.method("Caps", name="__getitem__")
def _caps_getitem(self: Any, index: int) -> Any:
    if index >= self.get_size():
        raise IndexError("structure index out of range")
    return self.get_structure(index)


@overlay.method("Caps", name="__iter__")
def _caps_iter(self: Any) -> Iterator[Any]:
    for i in range(self.get_size()):
        yield self.get_structure(i)


@overlay.method("Caps", name="__len__")
def _caps_len(self: Any) -> int:
    return int(self.get_size())


@overlay.method("Caps", name="__repr__")
def _caps_repr(self: Any) -> str:
    return f"<Gst.Caps {self}>"


# ---------------------------------------------------------------------------
# CapsFeatures
# ---------------------------------------------------------------------------


@overlay.method("CapsFeatures", name="__new__", as_staticmethod=True)
def _caps_features_new(cls: type, arg: Any = None) -> Any:
    if arg is None:
        return Gst.CapsFeatures.new_empty()
    if isinstance(arg, Gst.CapsFeatures):
        return arg.copy()
    if isinstance(arg, str):
        return Gst.CapsFeatures.from_string(arg)
    if isinstance(arg, (list, tuple)):
        features = Gst.CapsFeatures.new_empty()
        for item in arg:
            features.add(item)
        return features
    raise TypeError("wrong arguments when creating GstCapsFeatures object")


@overlay.method("CapsFeatures", name="__len__")
def _caps_features_len(self: Any) -> int:
    return int(self.get_size())


@overlay.method("CapsFeatures", name="__iter__")
def _caps_features_iter(self: Any) -> Iterator[str]:
    for index in range(len(self)):
        item = self.get_nth(index)
        if item is not None:
            yield item


@overlay.method("CapsFeatures", name="__getitem__")
def _caps_features_getitem(self: Any, index: int) -> str:
    if index < 0:
        index += len(self)
    if index < 0 or index >= len(self):
        raise IndexError("caps features index out of range")
    item = self.get_nth(index)
    if item is None:
        raise IndexError("caps features index out of range")
    return str(item)


@overlay.method("CapsFeatures", name="__contains__")
def _caps_features_contains(self: Any, item: object) -> bool:
    if not isinstance(item, str):
        return False
    return bool(self.contains(item))


@overlay.method("CapsFeatures", name="__repr__")
def _caps_features_repr(self: Any) -> str:
    if self.is_any():
        return "<Gst.CapsFeatures ANY>"
    return f"<Gst.CapsFeatures {list(self)!r}>"


# ---------------------------------------------------------------------------
# Fraction
# ---------------------------------------------------------------------------


@overlay.method("Fraction", name="__init__")
def _fraction_init(self: Any, num: int, denom: int = 1) -> None:
    def _gcd(a: int, b: int) -> int:
        while b:
            a, b = b, a % b
        return abs(a)

    self.num = num
    self.denom = denom

    if num < 0:
        num, denom = -num, -denom

    gcd = _gcd(num, denom)
    if gcd:
        self.num = num // gcd
        self.denom = denom // gcd

    self.type = "fraction"


@overlay.method("Fraction", name="__repr__")
def _fraction_repr(self: Any) -> str:
    return f"<Gst.Fraction {self}>"


@overlay.method("Fraction", name="__value__")
def _fraction_value(self: Any) -> float:
    return float(self.num) / float(self.denom)


@overlay.method("Fraction", name="__eq__")
def _fraction_eq(self: Any, other: object) -> bool:
    if isinstance(other, _FractionLike):
        left_num = int(self.num)
        left_denom = int(self.denom)
        right_num = int(other.num)
        right_denom = int(other.denom)
        return left_num * right_denom == right_num * left_denom
    return False


@overlay.method("Fraction", name="__ne__")
def _fraction_ne(self: Any, other: object) -> bool:
    if not isinstance(other, _FractionLike):
        return True
    left_num = int(self.num)
    left_denom = int(self.denom)
    right_num = int(other.num)
    right_denom = int(other.denom)
    return left_num * right_denom != right_num * left_denom


@overlay.method("Fraction", name="__mul__")
def _fraction_mul(self: _FractionLike, other: object) -> Gst.Fraction:
    left_num = int(self.num)
    left_denom = int(self.denom)
    if isinstance(other, _FractionLike):
        return Gst.Fraction(left_num * int(other.num), left_denom * int(other.denom))
    if isinstance(other, int):
        return Gst.Fraction(left_num * other, left_denom)
    raise TypeError(f"{type(other)} is not supported, use Gst.Fraction or int.")


@overlay.method("Fraction", name="__rmul__")
def _fraction_rmul(self: _FractionLike, other: object) -> Gst.Fraction:
    return _fraction_mul(self, other)


@overlay.method("Fraction", name="__truediv__")
def _fraction_truediv(self: _FractionLike, other: object) -> Gst.Fraction:
    left_num = int(self.num)
    left_denom = int(self.denom)
    if isinstance(other, _FractionLike):
        return Gst.Fraction(left_num * int(other.denom), left_denom * int(other.num))
    if isinstance(other, int):
        return Gst.Fraction(left_num, left_denom * other)
    raise TypeError(f"{type(other)} is not supported, use Gst.Fraction or int.")


@overlay.method("Fraction", name="__rtruediv__")
def _fraction_rtruediv(self: _FractionLike, other: object) -> Gst.Fraction:
    if isinstance(other, int):
        return Gst.Fraction(int(self.denom) * other, int(self.num))
    raise TypeError(f"{type(other)} is not an int.")


@overlay.method("Fraction", name="__float__")
def _fraction_float(self: Any) -> float:
    return float(self.num) / float(self.denom)


@overlay.method("Fraction", name="__str__")
def _fraction_str(self: Any) -> str:
    return f"{self.num}/{self.denom}"


# ---------------------------------------------------------------------------
# IntRange
# ---------------------------------------------------------------------------


@overlay.method("IntRange", name="__init__")
def _int_range_init(self: Any, r: range) -> None:
    if not isinstance(r, range):
        raise TypeError(f"{type(r)} is not a range.")
    if r.start >= r.stop:
        raise TypeError("Range start must be smaller then stop")
    if r.start % r.step != 0:
        raise TypeError("Range start must be a multiple of the step")
    if r.stop % r.step != 0:
        raise TypeError("Range stop must be a multiple of the step")
    self.range = r


@overlay.method("IntRange", name="__repr__")
def _int_range_repr(self: Any) -> str:
    return f"<Gst.IntRange [{self.range.start},{self.range.stop},{self.range.step}]>"


@overlay.method("IntRange", name="__str__")
def _int_range_str(self: Any) -> str:
    if self.range.step == 1:
        return f"[{self.range.start},{self.range.stop}]"
    return f"[{self.range.start},{self.range.stop},{self.range.step}]"


@overlay.method("IntRange", name="__eq__")
def _int_range_eq(self: Any, other: object) -> bool:
    current: range = self.range
    if isinstance(other, range):
        return current == other
    elif isinstance(other, _RangeLike):
        return current == other.range
    return False


# ---------------------------------------------------------------------------
# Int64Range
# ---------------------------------------------------------------------------


@overlay.method("Int64Range", name="__init__")
def _int64_range_init(self: Any, r: range) -> None:
    if not isinstance(r, range):
        raise TypeError(f"{type(r)} is not a range.")
    if r.start >= r.stop:
        raise TypeError("Range start must be smaller then stop")
    if r.start % r.step != 0:
        raise TypeError("Range start must be a multiple of the step")
    if r.stop % r.step != 0:
        raise TypeError("Range stop must be a multiple of the step")
    self.range = r


@overlay.method("Int64Range", name="__repr__")
def _int64_range_repr(self: Any) -> str:
    return f"<Gst.Int64Range [{self.range.start},{self.range.stop},{self.range.step}]>"


@overlay.method("Int64Range", name="__str__")
def _int64_range_str(self: Any) -> str:
    if self.range.step == 1:
        return f"(int64)[{self.range.start},{self.range.stop}]"
    return f"(int64)[{self.range.start},{self.range.stop},{self.range.step}]"


@overlay.method("Int64Range", name="__eq__")
def _int64_range_eq(self: Any, other: object) -> bool:
    current: range = self.range
    if isinstance(other, range):
        return current == other
    elif isinstance(other, _RangeLike):
        return current == other.range
    return False


# ---------------------------------------------------------------------------
# DoubleRange
# ---------------------------------------------------------------------------


@overlay.method("DoubleRange", name="__init__")
def _double_range_init(self: Any, start: float, stop: float) -> None:
    self.start = float(start)
    self.stop = float(stop)
    if start >= stop:
        raise TypeError("Range start must be smaller then stop")


@overlay.method("DoubleRange", name="__repr__")
def _double_range_repr(self: Any) -> str:
    return f"<Gst.DoubleRange [{self.start},{self.stop}]>"


@overlay.method("DoubleRange", name="__str__")
def _double_range_str(self: Any) -> str:
    return f"(double)[{self.start},{self.stop}]"


# ---------------------------------------------------------------------------
# FractionRange
# ---------------------------------------------------------------------------


@overlay.method("FractionRange", name="__init__")
def _fraction_range_init(self: Any, start: Any, stop: Any) -> None:
    if not isinstance(start, Gst.Fraction):
        raise TypeError(f"{type(start)} is not a Gst.Fraction.")
    if not isinstance(stop, Gst.Fraction):
        raise TypeError(f"{type(stop)} is not a Gst.Fraction.")
    if float(start) >= float(stop):
        raise TypeError("Range start must be smaller then stop")
    self.start = start
    self.stop = stop


@overlay.method("FractionRange", name="__repr__")
def _fraction_range_repr(self: Any) -> str:
    return f"<Gst.FractionRange [{self.start},{self.stop}]>"


@overlay.method("FractionRange", name="__str__")
def _fraction_range_str(self: Any) -> str:
    return f"(fraction)[{self.start},{self.stop}]"


# ---------------------------------------------------------------------------
# Bitmask
# ---------------------------------------------------------------------------


@overlay.method("Bitmask", name="__init__")
def _bitmask_init(self: Any, v: int) -> None:
    if not isinstance(v, int):
        raise TypeError(f"{type(v)} is not an int.")
    self.v = int(v)


@overlay.method("Bitmask", name="__str__")
def _bitmask_str(self: _BitmaskLike) -> str:
    return hex(self.v)


@overlay.method("Bitmask", name="__eq__")
def _bitmask_eq(self: _BitmaskLike, other: object) -> bool:
    if isinstance(other, _BitmaskLike):
        return bool(self.v == other.v)
    return bool(self.v == other)


# ---------------------------------------------------------------------------
# ValueArray
# ---------------------------------------------------------------------------


@overlay.method("ValueArray", name="__init__")
def _value_array_init(self: Any, array: list[Any] | None = None) -> None:
    self.array = list(array or [])


@overlay.method("ValueArray", name="append")
def _value_array_append(self: Any, item: Any) -> None:
    self.array.append(item)


@overlay.method("ValueArray", name="prepend")
def _value_array_prepend(self: Any, item: Any) -> None:
    self.array = [item] + self.array


@overlay.method("ValueArray", name="append_value", as_staticmethod=True)
def _value_array_append_value(this: Any, item: Any) -> None:
    this.append(item)


@overlay.method("ValueArray", name="prepend_value", as_staticmethod=True)
def _value_array_prepend_value(this: Any, item: Any) -> None:
    this.prepend(item)


@overlay.method("ValueArray", name="get_size", as_staticmethod=True)
def _value_array_get_size(this: Any) -> int:
    return len(this.array)


@overlay.method("ValueArray", name="get_value", as_staticmethod=True)
def _value_array_get_value(this: Any, index: int) -> Any:
    return this[index]


@overlay.method("ValueArray", name="__iter__")
def _value_array_iter(self: Any) -> Iterator[Any]:
    return iter(self.array)


@overlay.method("ValueArray", name="__getitem__")
def _value_array_getitem(self: Any, index: int) -> Any:
    return self.array[index]


@overlay.method("ValueArray", name="__setitem__")
def _value_array_setitem(self: Any, index: int, value: Any) -> None:
    self.array[index] = value


@overlay.method("ValueArray", name="__len__")
def _value_array_len(self: Any) -> int:
    return len(self.array)


@overlay.method("ValueArray", name="__str__")
def _value_array_str(self: Any) -> str:
    return "<" + ",".join(map(str, self.array)) + ">"


@overlay.method("ValueArray", name="__repr__")
def _value_array_repr(self: Any) -> str:
    return f"<Gst.ValueArray {self}>"


# ---------------------------------------------------------------------------
# ValueList
# ---------------------------------------------------------------------------


@overlay.method("ValueList", name="__init__")
def _value_list_init(self: Any, array: list[Any] | None = None) -> None:
    self.array = list(array or [])


@overlay.method("ValueList", name="append")
def _value_list_append(self: Any, item: Any) -> None:
    self.array.append(item)


@overlay.method("ValueList", name="prepend")
def _value_list_prepend(self: Any, item: Any) -> None:
    self.array = [item] + self.array


@overlay.method("ValueList", name="append_value", as_staticmethod=True)
def _value_list_append_value(this: Any, item: Any) -> None:
    this.append(item)


@overlay.method("ValueList", name="prepend_value", as_staticmethod=True)
def _value_list_prepend_value(this: Any, item: Any) -> None:
    this.prepend(item)


@overlay.method("ValueList", name="get_size", as_staticmethod=True)
def _value_list_get_size(this: Any) -> int:
    return len(this.array)


@overlay.method("ValueList", name="__iter__")
def _value_list_iter(self: Any) -> Iterator[Any]:
    return iter(self.array)


@overlay.method("ValueList", name="__getitem__")
def _value_list_getitem(self: Any, index: int) -> Any:
    return self.array[index]


@overlay.method("ValueList", name="__setitem__")
def _value_list_setitem(self: Any, index: int, value: Any) -> None:
    self.array[index] = value


@overlay.method("ValueList", name="__len__")
def _value_list_len(self: Any) -> int:
    return len(self.array)


@overlay.method("ValueList", name="__str__")
def _value_list_str(self: Any) -> str:
    return "{" + ",".join(map(str, self.array)) + "}"


@overlay.method("ValueList", name="__repr__")
def _value_list_repr(self: Any) -> str:
    return f"<Gst.ValueList {self}>"


# ---------------------------------------------------------------------------
# TagList
# ---------------------------------------------------------------------------


@overlay.method("TagList", name="__new__", as_staticmethod=True)
def _tag_list_new(cls: type) -> Any:
    return Gst.TagList.new_empty()


@overlay.method("TagList", name="__getitem__")
def _tag_list_getitem(self: Any, key: int | str) -> Any:
    if isinstance(key, int):
        index = key
        if index < 0:
            index += self.n_tags()
        if index < 0 or index >= self.n_tags():
            raise IndexError("taglist index out of range")
        tag_name = self.nth_tag_name(index)
    else:
        tag_name = key
    res, val = Gst.TagList.copy_value(self, tag_name)
    if not res:
        raise KeyError(f"tag {tag_name} not found")
    return val


@overlay.method("TagList", name="__setitem__")
def _tag_list_setitem(self: Any, key: str, value: Any) -> None:
    self.add_value(Gst.TagMergeMode.REPLACE, key, value)


@overlay.method("TagList", name="keys")
def _tag_list_keys(self: Any) -> set[str]:
    result: set[str] = set()

    def foreach(lst: Any, fid: str, udata: Any) -> bool:
        result.add(fid)
        return True

    self.foreach(foreach, None, None)
    return result


@overlay.method("TagList", name="items")
def _tag_list_items(self: Any) -> Iterator[tuple[str, Any]]:
    return iter(
        (key, Gst.TagList.copy_value(self, key)[1]) for key in _tag_list_keys(self)
    )


@overlay.method("TagList", name="enumerate")
def _tag_list_enumerate(self: Any) -> Iterator[tuple[str, Any]]:
    return _tag_list_items(self)


@overlay.method("TagList", name="__iter__")
def _tag_list_iter(self: Any) -> Iterator[str]:
    return iter(_tag_list_keys(self))


@overlay.method("TagList", name="__len__")
def _tag_list_len(self: Any) -> int:
    return int(self.n_tags())


@overlay.method("TagList", name="__str__")
def _tag_list_str(self: Any) -> str:
    return str(self.to_string())


@overlay.method("TagList", name="__repr__")
def _tag_list_repr(self: Any) -> str:
    return f"<Gst.TagList {self}>"


# ---------------------------------------------------------------------------
# BufferList
# ---------------------------------------------------------------------------


@overlay.method("BufferList", name="__len__")
def _buffer_list_len(self: Any) -> int:
    return int(self.length())


@overlay.method("BufferList", name="__getitem__")
def _buffer_list_getitem(self: Any, index: int) -> Any:
    if index < 0:
        index += len(self)
    if index < 0 or index >= len(self):
        raise IndexError("buffer list index out of range")
    return self.get(index)


@overlay.method("BufferList", name="__iter__")
def _buffer_list_iter(self: Any) -> Iterator[Any]:
    for index in range(len(self)):
        yield self[index]


@overlay.method("BufferList", name="__repr__")
def _buffer_list_repr(self: Any) -> str:
    return f"<Gst.BufferList len={len(self)}>"


# ---------------------------------------------------------------------------
# Sample
# ---------------------------------------------------------------------------


@overlay.method("Sample", name="__repr__")
def _sample_repr(self: Any) -> str:
    caps = self.get_caps()
    buffer = self.get_buffer()
    caps_text = caps.to_string() if caps is not None else "None"
    size = buffer.get_size() if buffer is not None else None
    return f"<Gst.Sample caps={caps_text!r} buffer_size={size}>"


# ---------------------------------------------------------------------------
# TIME_ARGS
# ---------------------------------------------------------------------------


def TIME_ARGS(time: int) -> str:
    if time == Gst.CLOCK_TIME_NONE:
        return "CLOCK_TIME_NONE"
    return "%u:%02u:%02u.%09u" % (
        time / (Gst.SECOND * 60 * 60),
        (time / (Gst.SECOND * 60)) % 60,
        (time / Gst.SECOND) % 60,
        time % Gst.SECOND,
    )


overlay.constant("TIME_ARGS", TIME_ARGS)


# ---------------------------------------------------------------------------
# init / deinit wrappers
# ---------------------------------------------------------------------------


@overlay.replace
def init(fn: Any, argv: list[str] | None = None) -> None:
    if not Gst.is_initialized():
        fn(argv or [])


@overlay.replace
def init_check(
    fn: Any,
    argv: list[str] | None = None,
) -> tuple[bool, list[str] | None]:
    if Gst.is_initialized():
        return True, argv
    success, parsed_argv = fn(argv or [])
    return bool(success), None if parsed_argv is None else list(parsed_argv)


@overlay.replace
def deinit(fn: Any) -> None:
    fn()


def init_python() -> None:
    if not Gst.is_initialized():
        raise NotInitialized(
            "Gst.init_python should never be called before GStreamer itself is initialized"
        )


overlay.constant("init_python", init_python)
