# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

"""GIR-XML → PEP 561 .pyi stub generator for ginext.

Coverage:
  * top-level functions, constants, aliases
  * enumerations and bitfields → IntEnum / IntFlag
  * classes / interfaces / records / unions, with:
      - constructors (named "new" → __init__; others → @classmethod)
      - methods (instance), static functions, properties
      - container element types (list[T], dict[K, V])
  * callbacks → typed Callable aliases
  * virtual methods → do_<name> chain-up helpers
  * GObject signals → typed connect/connect_after/emit @overloads keyed on
    Literal signal names, plus do_<signal> default-handler methods

Out parameters become tuple-typed returns (``tuple[ret, out1, out2, ...]``).
Two emission modes: ``native`` (the ``from ginext import <NS>`` surface, the
ginext-stubs package) and ``gi`` (the ``gi.repository`` pygobject-compat layer).
"""

from __future__ import annotations

import builtins as _builtins_mod
import tomllib
import xml.etree.ElementTree as ET
import re
from dataclasses import dataclass, field
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Literal

from .overlay_harvest import harvest_overlays

if TYPE_CHECKING:
    from collections.abc import Callable as _Callable

NS = {
    "gi": "http://www.gtk.org/introspection/core/1.0",
    "c": "http://www.gtk.org/introspection/c/1.0",
    "glib": "http://www.gtk.org/introspection/glib/1.0",
}

# Primitive GIR types → Python types. Anything not in here that's still a
# bare scalar gets mapped to Any (and the caller's namespace gets an import
# from typing).
PRIMITIVES: dict[str, str] = {
    "none": "None",
    "gboolean": "bool",
    "gchar": "int",
    "guchar": "int",
    "gint": "int",
    "guint": "int",
    "gshort": "int",
    "gushort": "int",
    "glong": "int",
    "gulong": "int",
    "gint8": "int",
    "guint8": "int",
    "gint16": "int",
    "guint16": "int",
    "gint32": "int",
    "guint32": "int",
    "gint64": "int",
    "guint64": "int",
    "gsize": "int",
    "gssize": "int",
    "gintptr": "int",
    "guintptr": "int",
    "goffset": "int",
    "gfloat": "float",
    "gdouble": "float",
    "utf8": "str",
    "filename": "str",
    "gunichar": "str",
    "gpointer": "int",
    "gconstpointer": "int",
    # GType isn't a primitive — it's a Python class implemented in C.
    # Resolved in _resolve_type() so we can pull in the right cross-namespace
    # qualification.
    # System types that appear bare in GIR but aren't declared as <alias>.
    # Modelled as ``int`` so signatures using them parse and check.
    "time_t": "int",
    "uid_t": "int",
    "gid_t": "int",
    "pid_t": "int",
    "off_t": "int",
    "ssize_t": "int",
    "size_t": "int",
    "intmax_t": "int",
    "uintmax_t": "int",
    "long double": "float",
    "unsigned": "int",
    "unsigned int": "int",
    "unsigned long": "int",
    "signed": "int",
}

# Python identifiers that can't be parameter names. We rename collisions to
# ``<name>_`` so the .pyi parses cleanly.
KEYWORDS = frozenset(
    {
        "False",
        "None",
        "True",
        "and",
        "as",
        "assert",
        "async",
        "await",
        "break",
        "class",
        "continue",
        "def",
        "del",
        "elif",
        "else",
        "except",
        "finally",
        "for",
        "from",
        "global",
        "if",
        "import",
        "in",
        "is",
        "lambda",
        "nonlocal",
        "not",
        "or",
        "pass",
        "raise",
        "return",
        "try",
        "while",
        "with",
        "yield",
        "match",
        "case",
    }
)

# Method / member names that would shadow Python builtins used elsewhere
# in the same class as type annotations. Without escaping, ``def int(self)
# -> int: ...`` makes subsequent ``-> int`` annotations resolve to the
# method (lexical scope), breaking mypy.

# Method / member names that shadow Python builtin TYPE names used as
# return-type annotations in the same class body (e.g. `def int(self) -> int:`
# would make the annotation `int` refer to the method). Only lowercase
# single-word type names that appear as GIR method names AND as annotation
# types in .pyi output are relevant — exceptions, warnings, and multi-word
# names are never confused with annotations.
#
# "bytes", "set", "range" are excluded: they appear as valid GIR method/field
# names (Pango.Coverage.set, Pango.AttrIterator.range, Gsk.ParseLocation.bytes)
# and their return types are different from the builtin, so they don't shadow.
_BUILTIN_EXCLUSIONS = frozenset(
    {
        "bytes",  # Gsk.ParseLocation.bytes, GLib.Bytes
        "set",  # Pango.Coverage.set
        "range",  # Pango.AttrIterator.range, Gdk.CicpParams.range
        "filter",  # Pango.AttrList.filter
    }
)
SHADOWED_BUILTINS = (
    frozenset(
        k
        for k in _builtins_mod.__dict__
        if (
            isinstance(getattr(_builtins_mod, k), type)
            and k.islower()  # only lowercase: int, str, float, bool, … not Exception
            and not k.startswith("_")
        )
    )
    - _BUILTIN_EXCLUSIONS
)


# Per-signal parameter type overrides: (namespace, class_name, signal_name, param_index)
# → replacement type expression.  Used when the GIR under-specifies a signal parameter
# (e.g. declares GObject.Object where the runtime always passes a more specific type).
# Prefer adding entries here over patching the GIR or overlay files.
_SIGNAL_PARAM_OVERRIDES: dict[tuple[str, str, str, int], str] = {
    # SignalListItemFactory signals always pass a Gtk.ListItem, not a bare
    # GObject.Object as the GIR declares.
    ("Gtk", "SignalListItemFactory", "setup", 0): "ListItem",
    ("Gtk", "SignalListItemFactory", "bind", 0): "ListItem",
    ("Gtk", "SignalListItemFactory", "unbind", 0): "ListItem",
    ("Gtk", "SignalListItemFactory", "teardown", 0): "ListItem",
}


def _ident(name: str | None) -> str:
    """Sanitise a GIR identifier for use as a Python parameter name."""
    if not name:
        return "_"
    if name[0].isdigit():
        name = "_" + name
    if name in KEYWORDS:
        return name + "_"
    # Hyphens appear in property names; replace before emitting.
    return name.replace("-", "_")


def _qualify(type_name: str, current_namespace: str) -> tuple[str, str | None]:
    """Map a GIR ``name="..."`` to a Python type expression.

    Returns ``(expr, import_namespace_or_None)``. The caller collects the
    namespaces in the second slot to emit ``from ginext import X`` (native) or
    ``from gi.repository import X`` (gi) at the top of the file.
    """
    if "." in type_name:
        other_ns, _, base = type_name.partition(".")
        if other_ns == current_namespace:
            return base, None
        return f"{other_ns}.{base}", other_ns
    return type_name, None


def _has_varargs(el: ET.Element) -> bool:
    """True if a callable takes C varargs (a ``<varargs>`` parameter).

    Variadic C functions are not introspectable — GObject-introspection cannot
    marshal ``...`` — so they are never callable from Python. GIR already marks
    them ``introspectable="0"``; this is the explicit, intent-revealing filter.
    """
    params = el.find("gi:parameters", NS)
    return params is not None and params.find("gi:parameter/gi:varargs", NS) is not None


@dataclass(frozen=True)
class DocRef:
    role: str
    target: str


def _callable_python_name(name: str | None) -> str:
    name = name or "_"
    if name in KEYWORDS or name in SHADOWED_BUILTINS:
        return name + "_"
    # GIR method names starting with a digit are not valid Python identifiers.
    if name and name[0].isdigit():
        return "_" + name
    return name


def _gtk_doc_to_plain(
    text: str,
    *,
    c_identifiers: dict[str, DocRef] | None = None,
    c_types: dict[str, str] | None = None,
    c_constants: dict[str, str] | None = None,
) -> str:
    """Convert the common gtk-doc subset into PyCharm-friendly RST.

    PyCharm renders reStructuredText docstrings with Docutils and can use a
    Sphinx working directory for richer roles. Prefer standard Python-domain
    roles where they map cleanly, and fall back to RST literals for GTK-only
    concepts such as signal names.
    """

    c_identifiers = c_identifiers or {}
    c_types = c_types or {}
    c_constants = c_constants or {}

    text = _markdown_fences_to_rst(text)
    text, links = _extract_markdown_links(text)

    def _xref(match: re.Match[str]) -> str:
        kind = match.group("kind")
        target = match.group("target")
        if kind == "property":
            return f":attr:`{target.replace(':', '.')}`"
        if kind == "signal":
            return f"``{target}``"
        if kind == "vfunc":
            head, sep, tail = target.rpartition(".")
            if sep:
                return f":meth:`{head}.do_{tail}`"
            return f":meth:`do_{target}`"
        if kind in {"func", "method", "ctor"}:
            role = "func" if kind == "func" else "meth"
            return f":{role}:`{target}`"
        if kind == "const":
            return f":data:`{target}`"
        return f":class:`{target}`"

    text = re.sub(
        r"\[`?(?P<kind>func|method|ctor|const|type|class|iface|struct|enum|flags|callback|error|property|signal|vfunc)@(?P<target>[^\]`\[\n]+)`?\]",
        _xref,
        text,
    )
    text = re.sub(r"\[(?:method|ctor)@([A-Za-z_][A-Za-z0-9_.:]*)", r":meth:`\1`", text)
    text = re.sub(r"\[func@([A-Za-z_][A-Za-z0-9_.:]*)", r":func:`\1`", text)
    text = re.sub(r"\[const@([A-Za-z_][A-Za-z0-9_.:]*)", r":data:`\1`", text)
    text = re.sub(
        r"\[(?:type|class|iface|struct|enum|flags)@([A-Za-z_][A-Za-z0-9_.:]*)",
        r":class:`\1`",
        text,
    )
    text = re.sub(
        r"\[property@([A-Za-z_][A-Za-z0-9_.:-]*)",
        lambda m: f":attr:`{m.group(1).replace(':', '.')}`",
        text,
    )
    text = re.sub(r"\[signal@([A-Za-z_][A-Za-z0-9_.:-]*)", r"``\1``", text)
    text, roles = _extract_rst_roles(text)
    text = _replace_c_doc_refs(
        text,
        c_identifiers=c_identifiers,
        c_types=c_types,
        c_constants=c_constants,
    )
    text, extra_roles = _extract_rst_roles(text, start=len(roles))
    roles.update(extra_roles)
    text = re.sub(r"(?<!`)`([^`\n]+)`(?!`)", r"``\1``", text)
    text = re.sub(r"@([A-Za-z_][A-Za-z0-9_]*)", r"``\1``", text)

    def _constant(match: re.Match[str]) -> str:
        value = match.group(1)
        if value == "TRUE":
            return "``True``"
        if value == "FALSE":
            return "``False``"
        if value in {"NULL", "nullptr"}:
            return "``None``"
        if value in c_constants:
            return f":data:`{c_constants[value]}`"
        return f"``{value}``"

    text = re.sub(r"%([A-Za-z_][A-Za-z0-9_]*)", _constant, text)
    text = re.sub(r"``(?:NULL|nullptr)``", "``None``", text)
    text = re.sub(r"``TRUE``", "``True``", text)
    text = re.sub(r"``FALSE``", "``False``", text)
    text = re.sub(r"#(?:NULL|nullptr)", "``None``", text)
    text = re.sub(r"#TRUE", "``True``", text)
    text = re.sub(r"#FALSE", "``False``", text)
    text = re.sub(r"#([A-Z][A-Za-z0-9_:.]*)", r":class:`\1`", text)
    text = text.replace("````", "``")
    for token, replacement in roles.items():
        text = text.replace(token, replacement)
    for token, replacement in links.items():
        text = text.replace(token, replacement)
    text = re.sub(
        r"``(:(?:class|meth|func|attr|data|obj):`[^`]+`)([^`]*)``",
        lambda m: (
            m.group(1) + (f" ``{m.group(2).strip()}``" if m.group(2).strip() else "")
        ),
        text,
    )
    return text


def _replace_c_doc_refs(
    text: str,
    *,
    c_identifiers: dict[str, DocRef],
    c_types: dict[str, str],
    c_constants: dict[str, str],
) -> str:
    """Rewrite gtk-doc C identifiers to the generated Python surface."""

    if c_identifiers:
        # Empty-call references in prose are nicer as a single cross-reference:
        # ``g_file_info_get_content_type()`` -> ``:meth:`Gio.FileInfo.get_content_type```.
        ident_names = sorted(map(re.escape, c_identifiers), key=len, reverse=True)
        ident_pattern = "|".join(ident_names)

        def _empty_call(match: re.Match[str]) -> str:
            ref = c_identifiers[match.group("name")]
            return f":{ref.role}:`{ref.target}`"

        text = re.sub(
            rf"\b(?P<name>{ident_pattern})\s*\(\s*\)",
            _empty_call,
            text,
        )

        def _identifier(match: re.Match[str]) -> str:
            ref = c_identifiers[match.group(0)]
            return f":{ref.role}:`{ref.target}`"

        text = re.sub(rf"\b(?:{ident_pattern})\b", _identifier, text)

    if c_types:
        type_names = sorted(map(re.escape, c_types), key=len, reverse=True)
        type_pattern = "|".join(type_names)

        def _type(match: re.Match[str]) -> str:
            return f":class:`{c_types[match.group('name')]}`"

        text = re.sub(
            rf"(?<![A-Za-z0-9_.])`?#?(?P<name>{type_pattern})\b`?",
            _type,
            text,
        )

    if c_constants:
        constant_names = sorted(map(re.escape, c_constants), key=len, reverse=True)
        constant_pattern = "|".join(constant_names)

        def _constant(match: re.Match[str]) -> str:
            return f":data:`{c_constants[match.group('name')]}`"

        text = re.sub(
            rf"(?<![A-Za-z0-9_.])`?[%#]@?(?P<name>{constant_pattern})\b`?",
            _constant,
            text,
        )

    return text


def _extract_markdown_links(text: str) -> tuple[str, dict[str, str]]:
    links: dict[str, str] = {}

    def _replace(match: re.Match[str]) -> str:
        token = f"<<GOI_LINK_TOKEN_{len(links)}>>"
        label = match.group(1).replace("`", "")
        url = match.group(2)
        links[token] = f"`{label} <{url}>`_"
        return token

    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", _replace, text)
    return text, links


def _extract_rst_roles(text: str, *, start: int = 0) -> tuple[str, dict[str, str]]:
    roles: dict[str, str] = {}

    def _replace(match: re.Match[str]) -> str:
        token = f"<<GOI_ROLE_TOKEN_{start + len(roles)}>>"
        roles[token] = match.group(0)
        return token

    text = re.sub(r":(?:class|meth|func|attr|data|obj):`[^`]+`", _replace, text)
    return text, roles


def _markdown_fences_to_rst(text: str) -> str:
    lines = text.splitlines()
    output: list[str] = []
    in_fence = False
    fence_lang = ""
    for line in lines:
        match = re.match(r"^```([A-Za-z0-9_+-]*)\s*$", line)
        if match:
            if not in_fence:
                fence_lang = match.group(1) or "text"
                output.append(f".. code-block:: {fence_lang}")
                output.append("")
                in_fence = True
            else:
                in_fence = False
                fence_lang = ""
            continue
        if in_fence:
            output.append(f"    {line}")
        else:
            output.append(line)
    if in_fence:
        output.append("")
    return "\n".join(output)


# ---------------------------------------------------------------------------
# IR
# ---------------------------------------------------------------------------


@dataclass
class Param:
    name: str
    type_expr: str
    direction: str  # "in", "out", "inout"
    nullable: bool
    has_default: bool
    doc: str | None = None


@dataclass
class Callable:
    name: str
    params: list[Param]
    return_expr: str
    out_exprs: list[str]
    is_constructor: bool = False
    is_static: bool = False
    is_throws: bool = False
    doc: str | None = None
    deprecated: bool = False
    deprecated_version: str | None = None
    # GIR ``moved-to="Class.method"`` on a namespace-level function: it is a
    # convenience duplicate of a type's static method. Used by the doc generator
    # to group it under the class instead of listing it as a global function.
    moved_to: str | None = None


@dataclass
class Property:
    name: str  # original, with hyphens
    py_name: str  # underscored
    type_expr: str
    # Settable at construction (writable / construct / construct-only). Drives
    # whether the property appears as a keyword in a GObject __init__.
    writable: bool = True
    deprecated: bool = False
    deprecated_version: str | None = None
    doc: str | None = None


@dataclass
class Klass:
    kind: str  # "class" | "interface" | "record" | "union"
    name: str
    parents: list[str]
    methods: list[Callable] = field(default_factory=list)
    virtual_methods: list[Callable] = field(default_factory=list)
    constructors: list[Callable] = field(default_factory=list)
    static_functions: list[Callable] = field(default_factory=list)
    properties: list[Property] = field(default_factory=list)
    signals: list[Signal] = field(default_factory=list)
    doc: str | None = None
    # GObject-derived classes accept arbitrary property kwargs in __init__;
    # plain records / unions don't. Set by the parser based on the presence
    # of glib:type-name (every GType-registered class has one).
    is_gobject: bool = False
    deprecated: bool = False
    deprecated_version: str | None = None


@dataclass
class EnumValue:
    name: str
    value: str
    doc: str | None = None


@dataclass
class Enum:
    name: str
    is_flags: bool
    values: list[EnumValue]
    deprecated: bool = False
    deprecated_version: str | None = None


@dataclass
class Constant:
    name: str
    type_expr: str
    value: str | None
    doc: str | None = None


@dataclass
class Alias:
    name: str
    target_expr: str


@dataclass
class CallbackType:
    name: str
    params: list[Param]
    return_expr: str


@dataclass
class Signal:
    name: str  # original GObject signal name, e.g. "activate-link"
    params: list[Param]
    return_expr: str
    doc: str | None = None
    # G_SIGNAL_ACTION: emittable by calling it (obj.clicked()); drives whether
    # the native descriptor is callable (_SignalMethod) or not (_Signal).
    action: bool = False
    deprecated: bool = False
    deprecated_version: str | None = None


@dataclass
class Namespace:
    name: str
    version: str
    classes: list[Klass] = field(default_factory=list)
    enums: list[Enum] = field(default_factory=list)
    constants: list[Constant] = field(default_factory=list)
    aliases: list[Alias] = field(default_factory=list)
    callbacks: list[CallbackType] = field(default_factory=list)
    functions: list[Callable] = field(default_factory=list)
    foreign_namespaces: set[str] = field(default_factory=set)
    uses_pathlike: bool = False


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


class Parser:
    def __init__(
        self,
        gir_path: Path,
        overlay: dict[str, Any] | None = None,
        *,
        doc_format: Literal["rst", "raw"] = "rst",
    ):
        self.gir_path = gir_path
        # ``rst`` (default) converts gtk-doc to PyCharm-friendly RST for the
        # .pyi docstrings; ``raw`` keeps the original gtk-doc text so the doc
        # generator (docgen.DocEmitter) can render its own Markdown with full
        # knowledge of the page layout and cross-reference targets.
        self.doc_format = doc_format
        self.root = ET.parse(gir_path).getroot()
        ns_el = self.root.find("gi:namespace", NS)
        if ns_el is None:
            raise ValueError(f"{gir_path}: no <namespace>")
        self.ns_name = ns_el.get("name") or ""
        self.ns_version = ns_el.get("version") or ""
        self.ns_el = ns_el
        self.foreign: set[str] = set()
        # TOML overlay data. None means "no overlay file applied" — separate
        # from an empty dict which would explicitly clear settings.
        self.overlay: dict[str, Any] = overlay or {}
        # Names actually declared (and introspectable) in this namespace.
        # GIR aliases sometimes reference types whose definitions are
        # marked ``introspectable="0"`` and therefore never emitted —
        # falling back to ``Any`` here keeps the .pyi self-contained.
        self._declared_local: set[str] = set()
        # Bitfield (IntFlag) and enumeration (IntEnum) names in this namespace.
        # Widened to `FlagType | int` / `EnumType | int` since ginext's C
        # marshaller accepts any integer for enum/flags args (IntFlag is a
        # subtype of int but int is not a subtype of IntFlag/IntEnum, so we
        # must explicitly allow both directions for callers to pass raw ints).
        self._enum_like_types: set[str] = set()
        for child in ns_el:
            if child.get("introspectable") == "0":
                continue
            name = child.get("name")
            if name:
                self._declared_local.add(name)
                if child.tag in (
                    "{http://www.gtk.org/introspection/core/1.0}bitfield",
                    "{http://www.gtk.org/introspection/core/1.0}enumeration",
                ):
                    self._enum_like_types.add(name)
        self._doc_identifiers, self._doc_types, self._doc_constants = (
            self._build_doc_ref_maps()
        )
        # Callback typedefs whose first parameter is GObject.Object | None (the
        # "source object" — the GObject that initiated the async operation).
        # Populated during parse(); used to inline specialized Callable types when
        # emitting methods on a concrete class (e.g. File.mount_enclosing_volume
        # gets Callable[[File | None, AsyncResult], None] instead of the typedef).
        self._source_generic_cbs: dict[str, CallbackType] = {}
        # Set to True when any filename input param emits the PathLike union;
        # the Emitter reads this via ns.uses_pathlike to add `import os`.
        self._uses_pathlike: bool = False

    # ---- type resolution ----

    def _deprecation(self, el: ET.Element) -> tuple[bool, str | None]:
        """Return (is_deprecated, deprecated_version) from a GIR element."""
        if el.get("deprecated") != "1":
            return False, None
        return True, el.get("deprecated-version")

    def _doc(self, el: ET.Element) -> str | None:
        doc_el = el.find("gi:doc", NS)
        if doc_el is None or not doc_el.text:
            return None
        if self.doc_format == "raw":
            return dedent(doc_el.text).strip() or None
        doc = _gtk_doc_to_plain(
            dedent(doc_el.text).strip(),
            c_identifiers=self._doc_identifiers,
            c_types=self._doc_types,
            c_constants=self._doc_constants,
        )
        return doc or None

    def doc_ref_maps(
        self,
    ) -> tuple[dict[str, DocRef], dict[str, str], dict[str, str]]:
        """Public view of the doc cross-reference maps (C name → Python target).

        Consumed by :class:`ginext_stubgen.docgen.DocEmitter` to resolve legacy
        gtk-doc identifiers (``gtk_window_new``, ``#GtkWidget``, ``%G_FOO``).
        """
        return self._doc_identifiers, self._doc_types, self._doc_constants

    def _build_doc_ref_maps(
        self,
    ) -> tuple[dict[str, DocRef], dict[str, str], dict[str, str]]:
        identifiers: dict[str, DocRef] = {}
        types: dict[str, str] = {}
        constants: dict[str, str] = {}

        def py_path(name: str) -> str:
            return f"{self.ns_name}.{name}"

        def add_type(el: ET.Element, name: str) -> None:
            target = py_path(name)
            for attr in ("type", "type-name"):
                value = el.get(f"{{{NS['glib']}}}{attr}")
                if value:
                    types[value] = target
            c_type = el.get(f"{{{NS['c']}}}type")
            if c_type:
                types[c_type] = target

        def add_callable(el: ET.Element, target: str, role: str) -> None:
            c_identifier = el.get(f"{{{NS['c']}}}identifier")
            if c_identifier:
                identifiers[c_identifier] = DocRef(role=role, target=target)

        for child in self.ns_el:
            if child.get("introspectable") == "0":
                continue
            tag = child.tag.split("}", 1)[-1]
            name = child.get("name")
            if not name:
                continue
            if tag == "function":
                add_callable(child, py_path(_callable_python_name(name)), "func")
            elif tag == "constant":
                c_type = child.get(f"{{{NS['c']}}}type")
                if c_type:
                    constants[c_type] = py_path(name)
            elif tag in (
                "class",
                "interface",
                "record",
                "union",
                "enumeration",
                "bitfield",
            ):
                add_type(child, name)
                for nested in child:
                    nested_tag = nested.tag.split("}", 1)[-1]
                    nested_name = nested.get("name")
                    if not nested_name or nested.get("introspectable") == "0":
                        continue
                    if nested_tag in ("method", "constructor", "function"):
                        target = f"{self.ns_name}.{name}.{_callable_python_name(nested_name)}"
                        add_callable(nested, target, "meth")
                    elif nested_tag == "virtual-method":
                        target = f"{self.ns_name}.{name}.do_{_callable_python_name(nested_name)}"
                        add_callable(nested, target, "meth")
                    elif nested_tag == "member":
                        c_identifier = nested.get(f"{{{NS['c']}}}identifier")
                        if c_identifier:
                            constants[c_identifier] = (
                                f"{self.ns_name}.{name}.{nested_name.upper()}"
                            )

        return identifiers, types, constants

    def _type_expr(
        self,
        parent: ET.Element,
        *,
        widen_enums: bool = True,
        allow_pathlike: bool = False,
    ) -> str:
        """Resolve a <type>/<array> child into a Python type expr.

        ``widen_enums=False`` suppresses the ``| int`` widening for IntFlag/IntEnum
        types — used for signal callback parameter positions where the signal always
        emits the precise enum value, never a raw int.

        ``allow_pathlike=True`` widens ``filename`` GIR types to include
        ``os.PathLike`` — correct for input parameters (the C marshaller calls
        ``PyOS_FSPath``), not for return values (which come back as plain ``str``).
        """
        type_el = parent.find("gi:type", NS)
        if type_el is not None:
            return self._resolve_type(
                type_el, widen_enums=widen_enums, allow_pathlike=allow_pathlike
            )
        array_el = parent.find("gi:array", NS)
        if array_el is not None:
            child_type = array_el.find("gi:type", NS)
            if child_type is not None and child_type.get("name") == "guint8":
                return "bytes"
            inner = self._type_expr(
                array_el, widen_enums=widen_enums, allow_pathlike=allow_pathlike
            )
            return f"list[{inner}]"
        return "Any"

    def _resolve_type(
        self,
        type_el: ET.Element,
        *,
        widen_enums: bool = True,
        allow_pathlike: bool = False,
    ) -> str:
        name = type_el.get("name")
        if not name:
            return "Any"
        if name in PRIMITIVES:
            primitive = PRIMITIVES[name]
            if allow_pathlike and name == "filename":
                self._uses_pathlike = True
                return "str | bytes | os.PathLike[str] | os.PathLike[bytes]"
            return primitive
        if name == "GType":
            # PyGObject accepts a Python class wherever a GType is asked for
            # (auto-converted via the class's __gtype__ attribute) or an
            # explicit GObject.Type instance. Modelling as ``type |
            # GObject.Type`` covers both call styles.
            if self.ns_name == "GObject":
                return "type | Type"
            self.foreign.add("GObject")
            return "type | GObject.Type"
        if name == "GLib.List" or name == "GLib.SList":
            child = type_el.find("gi:type", NS)
            inner = self._resolve_type(child) if child is not None else "Any"
            return f"list[{inner}]"
        if name == "GLib.HashTable":
            children = type_el.findall("gi:type", NS)
            if len(children) == 2:
                k = self._resolve_type(children[0])
                v = self._resolve_type(children[1])
                return f"dict[{k}, {v}]"
            return "dict[Any, Any]"
        if name in ("GLib.Array", "GLib.PtrArray"):
            child = type_el.find("gi:type", NS)
            inner = self._resolve_type(child) if child is not None else "Any"
            return f"list[{inner}]"
        if name == "GLib.ByteArray":
            return "bytes"
        # cairo.Context is generic in pycairo (Context[_SomeSurface]); use the
        # base Surface as the type argument for GIR-derived references.
        if name == "cairo.Context":
            self.foreign.add("cairo")
            return "cairo.Context[cairo.Surface]"
        expr, foreign = _qualify(name, self.ns_name)
        if foreign:
            self.foreign.add(foreign)
        elif expr not in self._declared_local:
            # Same-namespace reference to an undeclared (e.g.
            # introspectable="0") type. Fall back to Any so the .pyi
            # parses without dangling references.
            return "Any"
        # IntFlag/IntEnum params are widened to `Type | int` because ginext's C
        # marshaller accepts a plain integer for all enum/flags args — EXCEPT in
        # signal callback positions (widen_enums=False), where the signal always
        # emits the precise enum value and a narrower handler annotation is valid.
        if widen_enums:
            if foreign:
                ns_enum_like = _foreign_enum_like(foreign)
                base_name = expr.split(".", 1)[-1] if "." in expr else expr
                if base_name in ns_enum_like:
                    return f"{expr} | int"
            elif expr in self._enum_like_types:
                return f"{expr} | int"
        # Generic classes (item-typed list models, etc.) carry a PEP 696
        # `default=Any` on their type var, so a bare reference resolves to
        # `Foo[Any]` automatically — no need to append [Any] here.
        return expr

    # ---- callables ----

    def _parse_params(
        self,
        callable_el: ET.Element,
        *,
        widen_enums: bool = True,
        enclosing_class: str | None = None,
    ) -> tuple[list[Param], list[str], bool]:
        params: list[Param] = []
        out_exprs: list[str] = []
        params_el = callable_el.find("gi:parameters", NS)
        if params_el is None:
            return params, out_exprs, False
        # PyGObject elides three classes of GIR parameter from the visible
        # signature, because the runtime fills them in or doesn't need them:
        #
        #   1. Array length companions — ``<array length="N">`` on a sibling
        #      param. PyGObject passes ``len(array)`` automatically.
        #   2. Callback user_data — referenced by ``closure="N"`` on a
        #      callback param. PyGObject's marshaller binds *args passed
        #      after the callback into a tuple and shovels them through.
        #   3. Callback destroy notifiers — ``destroy="N"`` on a callback
        #      param. PyGObject manages lifetime via the callback's scope.
        #
        # All three indices refer to the 0-based position among non-instance
        # <parameter> children.
        elided_indices: set[int] = set()
        # The return value can itself be a length-bearing array whose length
        # companion is an out-parameter (e.g. TreePath.get_indices fills an
        # ``int depth`` out-arg). ginext drops it at runtime, so elide it here
        # too — otherwise the length leaks into the rendered return tuple.
        ret_el = callable_el.find("gi:return-value", NS)
        if ret_el is not None:
            for array_el in ret_el.iter("{" + NS["gi"] + "}array"):
                length_idx = array_el.get("length")
                if length_idx is not None and length_idx.lstrip("-").isdigit():
                    elided_indices.add(int(length_idx))
        for p in params_el.findall("gi:parameter", NS):
            for array_el in p.iter("{" + NS["gi"] + "}array"):
                length_idx = array_el.get("length")
                if length_idx is not None and length_idx.lstrip("-").isdigit():
                    elided_indices.add(int(length_idx))
            closure_idx = p.get("closure")
            if closure_idx is not None and closure_idx.lstrip("-").isdigit():
                elided_indices.add(int(closure_idx))
            destroy_idx = p.get("destroy")
            if destroy_idx is not None and destroy_idx.lstrip("-").isdigit():
                elided_indices.add(int(destroy_idx))
        non_instance_idx = -1
        for p in params_el.findall("gi:parameter", NS):
            non_instance_idx += 1
            if non_instance_idx in elided_indices:
                continue
            name = p.get("name") or "_"
            direction = p.get("direction") or "in"
            nullable = p.get("nullable") == "1" or p.get("allow-none") == "1"
            type_expr = self._type_expr(
                p,
                widen_enums=widen_enums,
                allow_pathlike=(direction == "in"),
            )
            # Nullable in-params accept None; widen the type to `T | None` so
            # callers can pass `None` explicitly (common for Cancellable).
            if nullable and direction == "in" and type_expr != "Any":
                type_expr = f"{type_expr} | None"
            # Specialize source-generic callbacks: replace the typedef with an
            # inline Callable whose first param is the enclosing class (not the
            # generic GObject.Object).  Only applies to in-params on methods.
            if enclosing_class is not None and direction == "in":
                type_expr = self._specialize_source_callback(type_expr, enclosing_class)
            param = Param(
                name=_ident(name),
                type_expr=type_expr,
                direction=direction,
                nullable=nullable,
                has_default=nullable and direction == "in",
                doc=self._doc(p),
            )
            if direction == "in":
                params.append(param)
            elif direction == "out":
                out_exprs.append(type_expr)
            elif direction == "inout":
                params.append(param)
                out_exprs.append(type_expr)
        # Required params can't follow optional ones in Python: walk backwards
        # and drop ``has_default`` from any optional param that has a required
        # param after it. GIR marks nullability per-arg with no ordering
        # constraint, so this fixup is unavoidable.
        seen_required_after = False
        for param_item in reversed(params):
            if not param_item.has_default:
                seen_required_after = True
            elif seen_required_after:
                param_item.has_default = False
        return params, out_exprs, False

    def _parse_callable(
        self,
        el: ET.Element,
        *,
        is_constructor: bool = False,
        is_static: bool = False,
        enclosing_class: str | None = None,
    ) -> Callable:
        name = _callable_python_name(el.get("name"))
        params, outs, _ = self._parse_params(el, enclosing_class=enclosing_class)
        ret_el = el.find("gi:return-value", NS)
        # Return types are NOT widened with | int: callers receive the precise
        # enum/flag value that the C function returns, not a raw integer.
        ret_expr = (
            self._type_expr(ret_el, widen_enums=False) if ret_el is not None else "None"
        )
        if ret_el is not None:
            nullable_return = (
                ret_el.get("nullable") == "1" or ret_el.get("allow-none") == "1"
            )
            if nullable_return and ret_expr not in ("None", "Any"):
                ret_expr = f"{ret_expr} | None"
        throws = el.get("throws") == "1"
        dep, dep_ver = self._deprecation(el)
        return Callable(
            name=name,
            params=params,
            return_expr=ret_expr,
            out_exprs=outs,
            is_constructor=is_constructor,
            is_static=is_static,
            is_throws=throws,
            doc=self._doc(el),
            deprecated=dep,
            deprecated_version=dep_ver,
            moved_to=el.get("moved-to"),
        )

    # ---- top-level walking ----

    def parse(self) -> Namespace:
        out = Namespace(name=self.ns_name, version=self.ns_version)
        # Pre-pass: collect source-generic callbacks (those whose first param is
        # GObject.Object | None) so that _parse_class can specialize them inline.
        # This must happen before classes are parsed since callbacks may appear
        # after classes in GIR document order (e.g. Gio.AsyncReadyCallback
        # comes after Gio.AppInfo in Gio-2.0.gir).
        for el in self.ns_el:
            if el.tag.split("}", 1)[-1] != "callback":
                continue
            if el.get("introspectable") == "0":
                continue
            cb_type = self._parse_callback(el)
            if (
                cb_type.params
                and cb_type.params[0].type_expr == "GObject.Object | None"
            ):
                self._source_generic_cbs[cb_type.name] = cb_type
        # Top-level shadowed-by: ``signal_add`` (introspectable=0, shadowed-by
        # ``signal_add_full``) is the name PyGObject exposes; the
        # introspectable companion ``signal_add_full`` is the binding stand-in.
        # Same logic as for class methods — invert the rename so the .pyi
        # carries the user-visible name with the introspectable signature.
        ns_rename: dict[str, str] = {}
        for el in self.ns_el:
            if el.tag.split("}", 1)[-1] != "function":
                continue
            if el.get("introspectable") != "0":
                continue
            shadowed_by = el.get("shadowed-by")
            orig_name = el.get("name")
            if shadowed_by and orig_name:
                ns_rename[shadowed_by] = orig_name
        for el in self.ns_el:
            tag = el.tag.split("}", 1)[-1]
            if el.get("introspectable") == "0" or _has_varargs(el):
                continue
            if tag == "function":
                cb = self._parse_callable(el, is_static=True)
                if cb.name in ns_rename:
                    cb.name = ns_rename[cb.name]
                out.functions.append(cb)
            elif tag == "constant":
                out.constants.append(self._parse_constant(el))
            elif tag == "alias":
                out.aliases.append(self._parse_alias(el))
            elif tag == "enumeration":
                out.enums.append(self._parse_enum(el, is_flags=False))
            elif tag == "bitfield":
                out.enums.append(self._parse_enum(el, is_flags=True))
            elif tag in ("class", "interface", "record", "union"):
                out.classes.append(self._parse_class(el, tag))
            elif tag == "callback":
                out.callbacks.append(self._parse_callback(el))
            # function-macro, docsection, boxed: skip for level 1.
        out.foreign_namespaces = self.foreign
        out.uses_pathlike = self._uses_pathlike
        return out

    def _parse_constant(self, el: ET.Element) -> Constant:
        return Constant(
            name=el.get("name") or "_",
            type_expr=self._type_expr(el),
            value=el.get("value"),
            doc=self._doc(el),
        )

    def _parse_alias(self, el: ET.Element) -> Alias:
        return Alias(name=el.get("name") or "_", target_expr=self._type_expr(el))

    def _parse_enum(self, el: ET.Element, *, is_flags: bool) -> Enum:
        values: list[EnumValue] = []
        for m in el.findall("gi:member", NS):
            name = (m.get("name") or "").upper()
            value = m.get("value") or "0"
            if not name:
                continue
            # Some GIR enum members start with a digit (G_FILE_ERROR_2BIG →
            # name="2big"); not a valid Python identifier. Prefix to keep
            # them addressable.
            if name[0].isdigit():
                name = "_" + name
            values.append(EnumValue(name=name, value=value, doc=self._doc(m)))
        dep, dep_ver = self._deprecation(el)
        return Enum(
            name=el.get("name") or "_",
            is_flags=is_flags,
            values=values,
            deprecated=dep,
            deprecated_version=dep_ver,
        )

    def _parse_class(self, el: ET.Element, kind: str) -> Klass:
        name = el.get("name") or "_"
        parents: list[str] = []
        parent_attr = el.get("parent")
        if parent_attr:
            expr, foreign = _qualify(parent_attr, self.ns_name)
            if foreign:
                self.foreign.add(foreign)
            parents.append(expr)
        for impl in el.findall("gi:implements", NS):
            iface = impl.get("name")
            if iface:
                expr, foreign = _qualify(iface, self.ns_name)
                if foreign:
                    self.foreign.add(foreign)
                parents.append(expr)
        is_gobject = (
            kind in ("class", "interface")
            and el.get("{http://www.gtk.org/introspection/glib/1.0}type-name")
            is not None
        )
        dep, dep_ver = self._deprecation(el)
        klass = Klass(
            kind=kind,
            name=name,
            parents=parents,
            is_gobject=is_gobject,
            doc=self._doc(el),
            deprecated=dep,
            deprecated_version=dep_ver,
        )
        # First pass: collect ``shadowed-by`` rename rules. When a method
        # has ``introspectable="0" shadowed-by="X"``, PyGObject (and goi)
        # still expose the *original* name at runtime — ``X`` is just GIR's
        # introspectable stand-in for binding generators. We want the
        # original name in the .pyi paired with X's signature.
        rename: dict[str, str] = {}  # introspectable name -> shadowed (original) name
        skip_introspectable: set[str] = set()
        for child in el:
            if child.tag.split("}", 1)[-1] != "method":
                continue
            if child.get("introspectable") != "0":
                continue
            shadowed_by = child.get("shadowed-by")
            orig_name = child.get("name")
            if shadowed_by and orig_name:
                rename[shadowed_by] = orig_name
                skip_introspectable.add(shadowed_by)

        for child in el:
            tag = child.tag.split("}", 1)[-1]
            if child.get("introspectable") == "0" or _has_varargs(child):
                continue
            if tag == "method":
                # Apply the rename rule: emit ``get_item`` from ``get_object``.
                name = child.get("name") or ""
                if name in rename:
                    cb = self._parse_callable(child, enclosing_class=klass.name)
                    cb.name = rename[name]
                    klass.methods.append(cb)
                    continue
            if tag == "constructor":
                klass.constructors.append(
                    self._parse_callable(
                        child, is_constructor=True, enclosing_class=klass.name
                    )
                )
            elif tag == "method":
                klass.methods.append(
                    self._parse_callable(child, enclosing_class=klass.name)
                )
            elif tag == "virtual-method":
                cb = self._parse_callable(child, enclosing_class=klass.name)
                cb.name = f"do_{cb.name}"
                klass.virtual_methods.append(cb)
            elif tag == "function":
                klass.static_functions.append(
                    self._parse_callable(child, is_static=True)
                )
            elif tag == "property":
                klass.properties.append(self._parse_property(child))
            elif tag == "field" and kind in ("record", "union"):
                # Records expose their C-struct fields directly
                # (``Gdk.Rectangle.width`` etc.); GObject classes hide them
                # behind <property> entries so we'd double up if we emitted
                # both. Stick to records/unions for level 1.
                field_prop = self._parse_field(child)
                if field_prop is not None:
                    klass.properties.append(field_prop)
            elif tag == "signal":
                # <glib:signal> — drives the typed connect/emit/do_ overloads.
                klass.signals.append(self._parse_signal(child))
        return klass

    def _parse_signal(self, el: ET.Element) -> Signal:
        name = el.get("name") or "_"
        # Signal callback parameters use widen_enums=False: the signal always
        # emits the precise enum/flag value (not a raw int), so a callback
        # annotated with the narrow enum type should pass mypy's contravariance
        # check. (Function params stay widened: callers CAN pass raw ints.)
        params, _, _ = self._parse_params(el, widen_enums=False)
        ret_el = el.find("gi:return-value", NS)
        # Signal return type also not widened (callback return value is precise).
        ret_expr = (
            self._type_expr(ret_el, widen_enums=False) if ret_el is not None else "None"
        )
        if ret_el is not None:
            nullable = ret_el.get("nullable") == "1" or ret_el.get("allow-none") == "1"
            if nullable and ret_expr not in ("None", "Any"):
                ret_expr = f"{ret_expr} | None"
        dep, dep_ver = self._deprecation(el)
        return Signal(
            name=name,
            params=params,
            return_expr=ret_expr,
            doc=self._doc(el),
            action=el.get("action") == "1",
            deprecated=dep,
            deprecated_version=dep_ver,
        )

    def _parse_field(self, el: ET.Element) -> Property | None:
        name = el.get("name")
        if not name:
            return None
        type_expr = self._type_expr(el)
        py_name = _ident(name)
        return Property(name=name, py_name=py_name, type_expr=type_expr)

    def _parse_property(self, el: ET.Element) -> Property:
        name = el.get("name") or "_"
        py_name = _ident(name)
        # A property can be passed to construction when it is writable or
        # construct(-only). GIR omits `writable` for read-only properties.
        writable = (
            el.get("writable") == "1"
            or el.get("construct") == "1"
            or el.get("construct-only") == "1"
        )
        dep, dep_ver = self._deprecation(el)
        return Property(
            name=name,
            py_name=py_name,
            type_expr=self._type_expr(el),
            writable=writable,
            deprecated=dep,
            deprecated_version=dep_ver,
            doc=self._doc(el),
        )

    def _parse_callback(self, el: ET.Element) -> CallbackType:
        name = el.get("name") or "_"
        params, _, _ = self._parse_params(el)
        # Strip trailing ``gpointer`` / ``int | None`` user_data params: ginext
        # elides the C user_data slot from all callbacks (it passes user data
        # via closures or ``owner=`` instead).  The GIR declares the full C
        # signature including data; the Python surface never sees it.
        while params and params[-1].type_expr in ("int | None", "Any"):
            params = params[:-1]
        ret_el = el.find("gi:return-value", NS)
        ret_expr = self._type_expr(ret_el) if ret_el is not None else "None"
        return CallbackType(name=name, params=params, return_expr=ret_expr)

    def _specialize_source_callback(self, type_expr: str, enclosing_class: str) -> str:
        """Inline-specialize a source-generic callback typedef for the enclosing class.

        ``AsyncReadyCallback`` is defined as ``Callable[[GObject.Object | None,
        AsyncResult], None]``.  When used as a method parameter on a concrete class
        (e.g. ``File.mount_enclosing_volume``), the source object is always that
        class, so we emit the more precise inline type instead of the typedef.
        """
        nullable = type_expr.endswith(" | None")
        base = type_expr[:-7] if nullable else type_expr
        # Accept both bare ("AsyncReadyCallback") and qualified ("Gio.AsyncReadyCallback").
        cb = self._source_generic_cbs.get(base)
        if cb is None:
            parts = base.split(".", 1)
            if len(parts) == 2:
                cb = self._source_generic_cbs.get(parts[1])
        if cb is None:
            return type_expr
        # Rebuild the Callable with the enclosing class replacing GObject.Object.
        rest = [p.type_expr for p in cb.params[1:]]
        inline = (
            f"Callable[[{enclosing_class} | None, {', '.join(rest)}], {cb.return_expr}]"
        )
        return f"{inline} | None" if nullable else inline


# ---------------------------------------------------------------------------
# Emitter
# ---------------------------------------------------------------------------

Mode = Literal["native", "gi"]


def render_signature(
    fn: Callable,
    *,
    instance: str | None,
    return_override: str | None = None,
) -> str:
    """Render a Callable as a Python ``(params) -> return`` signature string.

    Out-parameters fold into the return as ``tuple[ret, out1, ...]`` (PyGObject
    convention). Shared by the .pyi Emitter and the doc generator so an API page
    shows the exact signature the stub declares.
    """
    parts: list[str] = []
    if instance:
        parts.append(instance)
    for p in fn.params:
        base = f"{p.name}: {_widen_glib_bytes_input(p.type_expr)}"
        if p.has_default:
            base += " = ..."
        parts.append(base)
    ret = return_override if return_override is not None else fn.return_expr
    if fn.out_exprs:
        # If the function "returns" None, PyGObject only returns the out
        # params (as a tuple if multiple, bare if one). Modelling None
        # explicitly leads to ``tuple[None, X]`` which user code never
        # actually unpacks.
        base_parts = [] if ret == "None" else [ret]
        tuple_parts = base_parts + fn.out_exprs
        if len(tuple_parts) == 1:
            ret = tuple_parts[0]
        else:
            ret = f"tuple[{', '.join(tuple_parts)}]"
    return f"({', '.join(parts)}) -> {ret}"


def _widen_glib_bytes_input(type_expr: str) -> str:
    if type_expr.endswith(" | None"):
        base = type_expr[: -len(" | None")]
        widened = _widen_glib_bytes_input(base)
        if widened == base:
            return type_expr
        return f"{widened} | None"
    if type_expr == "bytes":
        return "bytes | list[int]"
    if type_expr == "Bytes":
        return "bytes | Bytes"
    if type_expr == "GLib.Bytes":
        return "bytes | GLib.Bytes"
    return type_expr


class Emitter:
    def __init__(self, ns: Namespace, *, mode: Mode = "native"):
        self.ns = ns
        self.mode = mode
        self.mode_overlays = _mode_overlays(mode)
        self.lines: list[str] = []
        # Own member names per class (methods/static/ctors/properties).
        self._by_name: dict[str, Klass] = {k.name: k for k in ns.classes}
        # Ancestor member names per class.
        self._ancestor_members: dict[str, set[str]] = {}
        for k in ns.classes:
            names: set[str] = set()
            stack = list(k.parents)
            visited: set[str] = set()
            while stack:
                pname = stack.pop()
                if "." in pname or pname in visited:
                    continue
                visited.add(pname)
                if pname in self._by_name:
                    pk = self._by_name[pname]
                    names |= {m.name for m in pk.methods}
                    names |= {f.name for f in pk.static_functions}
                    names |= {c.name for c in pk.constructors}
                    stack.extend(pk.parents)
            self._ancestor_members[k.name] = names
        self._own_members: dict[str, set[str]] = {
            k.name: (
                {m.name for m in k.methods}
                | {f.name for f in k.static_functions}
                | {c.name for c in k.constructors}
                | {p.py_name for p in k.properties}
            )
            for k in ns.classes
        }

    def _signal_backing_method_names(self, klass: Klass) -> set[str]:
        """Signal names whose py_name also appears as a real GIR method.

        The runtime exposes these as signal descriptors backed by a method, so
        the stub should emit SignalMethod rather than a plain Signal. This
        includes same-class collisions (Gtk.Dialog.response) and inherited
        method backings (Gio.SimpleAction.activate, Gtk.Entry.activate).
        """
        own = self._own_members.get(klass.name, set())
        inherited = self._ancestor_members.get(klass.name, set())
        signal_py_names = {_ident(s.name) for s in klass.signals}
        return (own | inherited) & signal_py_names

    def _signal_property_conflicts(self, klass: Klass) -> set[str]:
        """Signal names that clash with a same-class GIR property.

        A property and signal with the same name (e.g. DBusConnection.closed)
        can't both be emitted — skip the signal descriptor so the property
        type stands (the signal is still accessible via connect("name", cb)).
        """
        own_props = {p.py_name for p in klass.properties}
        return {_ident(s.name) for s in klass.signals} & own_props

    def _has_any_deprecated(self) -> bool:
        """True if any symbol in this namespace carries deprecated="1"."""
        for k in self.ns.classes:
            if k.deprecated:
                return True
            if any(
                m.deprecated
                for m in k.methods
                + k.virtual_methods
                + k.constructors
                + k.static_functions
            ):
                return True
            if any(p.deprecated for p in k.properties):
                return True
            if any(s.deprecated for s in k.signals):
                return True
        if any(e.deprecated for e in self.ns.enums):
            return True
        return bool(any(f.deprecated for f in self.ns.functions))

    def _dep(self, deprecated: bool, version: str | None, indent: str = "") -> None:
        """Emit a @deprecated(...) decorator line if the symbol is deprecated."""
        if not deprecated:
            return
        msg = f"Deprecated since {version}." if version else "Deprecated."
        self.lines.append(f'{indent}@deprecated("{msg}")')

    def emit(self) -> str:
        self._header()
        # Namespace-level prelude (e.g. GObject's _PropsProxy helper) from
        # native_overlays.toml. Emitted before any class so forward refs
        # ("_PropsProxy") resolve.
        ns_native = self._ns_overlay()
        prelude = ns_native.get("prelude")
        if isinstance(prelude, str) and prelude.strip():
            import re as _re

            # Replace ``Ns.Foo`` with bare ``Foo`` when Ns is this namespace —
            # overlay code uses qualified names but the stub uses bare names.
            ns_prefix = _re.escape(self.ns.name) + r"\."
            prelude = _re.sub(rf"\b{ns_prefix}", "", prelude)
            # Also strip Ns. inside string annotations (forward refs).
            prelude = prelude.replace(f"'{self.ns.name}.", "'")
            prelude = prelude.replace(f'"{self.ns.name}.', '"')
            # Overlay files often import ``from ginext import X as _X`` and use
            # ``_X.Type`` in annotations. Replace ``_Ns.`` with ``Ns.`` so the
            # stub uses the proper qualified name (which IS imported at the top).
            prelude = _re.sub(r"\b_([A-Z][A-Za-z0-9]*)\.", r"\1.", prelude)
            # Filter out lines that would redefine GIR-declared names
            # (e.g. ``Error = _GLibError`` when GIR already emits class Error)
            # or reference private runtime helpers not in the stub namespace.
            filtered: list[str] = []
            # All names that will be emitted from the GIR (classes, enums,
            # aliases, callbacks) or already defined in the TOML prelude —
            # harvested assignments to these would redefine them.
            gir_names = (
                {k.name for k in self.ns.classes}
                | {e.name for e in self.ns.enums}
                | {a.name for a in self.ns.aliases}
                | {c.name for c in self.ns.callbacks}
            )
            # Also collect names already defined in the TOML prelude so the
            # harvested overlay doesn't redefine what TOML already declared.
            toml_prelude = ns_native.get("prelude") or ""
            toml_defined: set[str] = set()
            for line in toml_prelude.splitlines():
                m_td = _re.match(r"^(?:class|def)\s+(\w+)", line)
                if m_td:
                    toml_defined.add(m_td.group(1))
            already_defined = gir_names | toml_defined
            for line in prelude.splitlines():
                m = _re.match(r"^(\w+)\s*[=:]", line)
                if m and m.group(1) in already_defined:
                    continue
                # Skip self-assignments ``Foo = Foo`` — they arise when the
                # overlay registers a Python-internal class as a namespace
                # constant; the class doesn't exist in the stub namespace.
                if _re.match(r"^(\w+) = \1\s*$", line):
                    continue
                filtered.append(line)
            cleaned = "\n".join(filtered).strip()
            if cleaned:
                self.lines.append(cleaned)
                self.lines.append("")
        emitted_alias_names: set[str] = set()
        for alias in self.ns.aliases:
            self._alias(alias)
            emitted_alias_names.add(alias.name)
        # Native ``replace_alias = true`` entries replace a GIR alias. When
        # the TOML overlay stripped the GIR alias (``kind = "internal"``)
        # the class still needs to be emitted — do it here.
        classes_native = ns_native.get("classes", {})
        if isinstance(classes_native, dict):
            for cname, cnative in classes_native.items():
                if not isinstance(cnative, dict):
                    continue
                if not cnative.get("replace_alias"):
                    continue
                if cname in emitted_alias_names:
                    continue
                self._alias(Alias(name=cname, target_expr=""))
                emitted_alias_names.add(cname)
        for enum in self.ns.enums:
            self._enum(enum)
        for cb in self.ns.callbacks:
            self._callback(cb)
        for klass in self.ns.classes:
            self._class(klass)
        for const in self.ns.constants:
            self._constant(const)
        # Suppress GIR-derived functions whose name appears in module_reserves
        # (i.e. the overlay's @replace/@add version already appeared in the
        # prelude and should win).
        module_reserves: set[str] = set(ns_native.get("module_reserves", []))
        for fn in self.ns.functions:
            if fn.name in module_reserves:
                continue
            self._function(fn)
        # Drop trailing blank lines.
        while self.lines and self.lines[-1] == "":
            self.lines.pop()
        return "\n".join(self.lines) + "\n"

    def _header(self) -> None:
        self.lines.append(
            f"# Auto-generated by ginext-stubgen from {self.ns.name}-{self.ns.version}.gir."
        )
        self.lines.append("# Do not edit by hand.")
        # GI's multiple inheritance produces inherently incompatible override
        # signatures (subclasses specialise return types / parameters) and
        # references to generic types without explicit type-args. Both are
        # intentional and runtime-correct; suppress them file-wide so the stub
        # stays clean where these patterns are irreducible (see typing-debt.md).
        # ``valid-type`` covers cases where a GIR field/method name is also a
        # Python builtin type name (e.g. ``bytes``, ``filter``); within a class
        # body the field name shadows the builtin, making e.g.
        # ``def f(self, x: bytes)`` resolve ``bytes`` to the field not the type.
        self.lines.append(
            '# mypy: disable-error-code="assignment,explicit-any,misc,name-defined,no-redef,override,type-arg,untyped-decorator,valid-type"'
        )
        self.lines.append("from __future__ import annotations")
        self.lines.append("")
        if self.ns.uses_pathlike:
            self.lines.append("import os")
        self.lines.append("from collections.abc import Iterator")
        has_deprecated = self._has_any_deprecated()
        if has_deprecated:
            self.lines.append("from typing_extensions import deprecated")
        native_signals = self.mode != "gi" and any(k.signals for k in self.ns.classes)
        if native_signals:
            self.lines.append("from contextlib import AbstractContextManager")
            # ParamSpec aliased: GObject defines its own `ParamSpec` class, so
            # the bare typing name would clash in GObject.pyi.
            self.lines.append(
                "from typing import Any, Awaitable, Callable, ClassVar, Generic, "
                "Final, Literal, NamedTuple, ParamSpec as _ParamSpec, Self, TypeVar, override, overload"
            )
        else:
            self.lines.append(
                "from typing import Any, Awaitable, Callable, ClassVar, Final, Generic, Literal, "
                "NamedTuple, Self, TypeVar, override, overload"
            )
        # native: `from ginext import <NS>` (the flat runtime surface);
        # gi: `from gi.repository import <NS>` (pygobject compat).
        # cairo is always imported directly as pycairo — never via ginext.
        package = "gi.repository" if self.mode == "gi" else "ginext"
        for foreign in sorted(self.ns.foreign_namespaces):
            if foreign == self.ns.name:
                continue
            if foreign == "cairo":
                self.lines.append("import cairo")
            else:
                self.lines.append(f"from {package} import {foreign}")
        if self.mode != "gi":
            # ginext augments every namespace object with `.overlay` (the
            # OverlayRegistrar used to register overlays) and every metaclass-
            # built class with `.gimeta` (GIMeta). Model both so ginext's own
            # _overlays/*.py and `cls.gimeta` access type-check.
            self.lines.append(
                "from ginext.overlay.registrar import "
                "OverlayRegistrar as _OverlayRegistrar"
            )
            self.lines.append("from ginext.private import GIMeta")
            self.lines.append("")
            self.lines.append("overlay: _OverlayRegistrar")
            # ginext exposes the underlying typelib version as a tuple on every namespace.
            self.lines.append("__version__: tuple[int, ...]")
            # Fallback for dynamically-installed names (GEnum, GFlags, error classes,
            # deprecated aliases, etc.) that aren't in the GIR or the overlay stubs.
            self.lines.append("def __getattr__(name: str) -> Any: ...")
        self.lines.append("")
        if native_signals:
            self._emit_signal_helpers()

    def _emit_signal_helpers(self) -> None:
        # Generic signal descriptors backing `obj.<signal>` in native mode.
        # _Signal connects/emits; _SignalMethod also emits when called (an
        # action signal, e.g. button.clicked()). Owner is the emitting class,
        # so a handler is typed Callable[[Owner, *signal-args], ret].
        # Public TypeVars — no leading underscore so users can write e.g.
        # ``Callable[[GObject.Object, GObject.ParamSpec], None]`` in callbacks.
        if self.ns.name != "GObject":
            self.lines.append(
                "from ginext.GObject import SignalConnection, Signal, SignalMethod, DetailedSignal"
            )
            self.lines.append("")
            return

        self.lines.append("SigO = TypeVar('SigO')")
        self.lines.append("_SigP = _ParamSpec('_SigP')")
        self.lines.append("SigR = TypeVar('SigR')")
        self.lines.append("")
        # In .pyi stubs, properties are declared as bare typed attributes;
        # @property is not needed and triggers [untyped-decorator].
        self.lines.append("class SignalConnection:")
        self.lines.append("    handler_id: int")
        self.lines.append("    signal_name: str")
        self.lines.append("    source: Any")
        self.lines.append("    callback: Callable[..., Any]")
        self.lines.append("    after: bool")
        self.lines.append("    once: bool")
        self.lines.append("    owner: Any")
        self.lines.append("    is_connected: bool")
        self.lines.append("    def disconnect(self) -> None: ...")
        self.lines.append(
            "    def blocked(self) -> AbstractContextManager[SignalConnection]: ..."
        )
        self.lines.append("")
        # Public signal types — no leading underscore so downstream code can
        # annotate callbacks as e.g. ``def cb(sig: Signal[Widget, ...])``.
        # Signal = connect/emit only.
        # SignalMethod = also callable (method-backed signals).
        # DetailedSignal = callable with a detail key → returns scoped Signal.
        self.lines.append("class Signal(Generic[SigO, _SigP, SigR]):")
        self.lines.append(
            "    def __call__(self, *args: _SigP.args, **kwargs: _SigP.kwargs) "
            "-> SigR: ..."
        )
        self.lines.append(
            "    def connect(self, handler: Callable[..., object], *, after: bool = ..., once: bool = ..., owner: Any = ...) -> SignalConnection: ..."
        )
        self.lines.append(
            "    def connect_after(self, handler: Callable[..., object]) -> SignalConnection: ..."
        )
        self.lines.append(
            "    def emit(self, *args: _SigP.args, **kwargs: _SigP.kwargs) -> "
            "SigR: ..."
        )
        self.lines.append(
            "    def disconnect(self, connection: SignalConnection) -> None: ..."
        )
        self.lines.append("class SignalMethod(Signal[SigO, _SigP, SigR]):")
        self.lines.append(
            "    def __call__(self, *args: _SigP.args, **kwargs: _SigP.kwargs) "
            "-> SigR: ..."
        )
        self.lines.append("")
        self.lines.append("class DetailedSignal(Signal[SigO, _SigP, SigR]):")
        self.lines.append(
            "    def __call__(self, detail: str | GObject.Property) -> "
            "'Signal[SigO, _SigP, SigR]': ..."
        )
        self.lines.append("")

    def _alias(self, alias: Alias) -> None:
        # If native_overlays.toml flags this alias as ``replace_alias = true``,
        # the actual Python type is a hand-written class (e.g. GObject.Type
        # is a GoiGType wrapper, not an integer). The replacement emission
        # happens through the normal class loop after a synthetic Klass is
        # inserted from native_overlays — see _emit_native_replacement_classes.
        ns_native = self._ns_overlay()
        class_native = ns_native.get("classes", {}).get(alias.name, {})
        if isinstance(class_native, dict) and class_native.get("replace_alias"):
            self.lines.append(f"class {alias.name}:")
            body = class_native.get("body", "")
            if isinstance(body, str) and body.strip():
                for line in body.rstrip().splitlines():
                    self.lines.append("    " + line if line else "")
            else:
                self.lines.append("    pass")
            self.lines.append("")
            return
        # Aliases like ``<alias name="MainContextPusher"><type name="none"/>``
        # describe opaque types whose C definition is just ``void``.
        # Emit an empty class so they're still usable as a type annotation.
        if alias.target_expr == "None":
            self.lines.append(f"class {alias.name}:")
            self.lines.append("    pass")
            self.lines.append("")
            return
        self.lines.append(f"{alias.name} = {alias.target_expr}")

    def _enum(self, enum: Enum) -> None:
        base = "IntFlag" if enum.is_flags else "IntEnum"
        self._ensure_enum_import()
        self._dep(enum.deprecated, enum.deprecated_version)
        self.lines.append(f"class {enum.name}({base}):")
        if not enum.values:
            self.lines.append("    pass")
        else:
            for v in enum.values:
                self.lines.append(f"    {v.name} = {v.value}")
        self.lines.append("")

    def _ensure_enum_import(self) -> None:
        # Inject `from enum import IntEnum, IntFlag` once.
        marker = "from enum import IntEnum, IntFlag"
        if marker in self.lines:
            return
        # Place under the typing import.
        for i, line in enumerate(self.lines):
            if line.startswith("from typing import"):
                self.lines.insert(i + 1, marker)
                return
        self.lines.insert(0, marker)

    def _callback(self, cb: CallbackType) -> None:
        param_types = ", ".join(p.type_expr for p in cb.params)
        self.lines.append(f"{cb.name} = Callable[[{param_types}], {cb.return_expr}]")

    def _constant(self, const: Constant) -> None:
        self.lines.append(f"{const.name}: {const.type_expr}")
        if const.doc:
            self._docstring("", const.doc)

    def _function(self, fn: Callable) -> None:
        if self._emit_async_overloads(
            callable_map={f.name: f for f in self.ns.functions},
            fn=fn,
            indent="",
            instance=None,
        ):
            return
        self._dep(fn.deprecated, fn.deprecated_version)
        sig = self._signature(fn, instance=None)
        self._callable_def("", f"def {_ident(fn.name)}{sig}", doc=fn.doc)

    def _class(self, klass: Klass) -> None:
        # Native overlay for this class — extra bases, hand-written body
        # block, and the list of names ``reserves`` for which generation of
        # GIR-derived members is suppressed (so an augmented ``connect`` in
        # ``Object`` isn't redefined or trip override-checks in subclasses).
        ns_native = self._ns_overlay()
        class_native = ns_native.get("classes", {}).get(klass.name, {})
        if not isinstance(class_native, dict):
            class_native = {}
        # `item_type = "_T"` (generic) or a concrete type parameterizes a list
        # model: rewrite the class's item-typed members before bases/methods
        # are emitted. Hand-written `body`/`reserves` still override.
        item_type = class_native.get("item_type")
        if isinstance(item_type, str) and item_type:
            self._apply_item_type(klass, item_type)
        base_override = class_native.get("bases")
        if isinstance(base_override, list):
            bases_list = [base for base in base_override if isinstance(base, str)]
        else:
            bases_list = list(klass.parents)
        extra_bases = class_native.get("extra_bases", [])
        if isinstance(extra_bases, list):
            for base in extra_bases:
                if isinstance(base, str) and base not in bases_list:
                    bases_list.append(base)
        bases = ", ".join(bases_list)
        header = f"class {klass.name}" + (f"({bases})" if bases else "") + ":"
        # GIR multiple inheritance often combines bases that expose the same
        # C symbol through incompatible Python signatures; misc/type-arg are
        # suppressed file-wide so no per-class suffix is needed.
        self._dep(klass.deprecated, klass.deprecated_version)
        self.lines.append(header)
        body_started = False
        if klass.doc:
            self._docstring("    ", klass.doc)
            body_started = True
        # Track names already defined in this class body — GIR sometimes
        # exposes the same name as both a <property> and a <method>
        # (Pango.Font has ``is_variable`` as both). Keep the first (whichever
        # the parser ordered) and skip duplicates.
        seen: set[str] = set()

        def _take(name: str) -> bool:
            if name in seen:
                return False
            seen.add(name)
            return True

        body = class_native.get("body")
        if isinstance(body, str) and body.strip():
            # Strip self-namespace prefix from string annotations in body content.
            body = body.replace(f"'{self.ns.name}.", "'")
            body = body.replace(f'"{self.ns.name}.', '"')
            body_lines = self._overlay_body_lines_with_docs(body, klass)
            for line in body_lines:
                self.lines.append("    " + line if line else "")
            reserves = class_native.get("reserves", [])
            if isinstance(reserves, list):
                for name in reserves:
                    if isinstance(name, str):
                        seen.add(name)
            body_started = True
        # ginext's metaclass attaches `.gimeta` (GIMeta) to every built class;
        # it is read off the class object (`cls.gimeta`), so declare a ClassVar.
        if self.mode != "gi" and _take("gimeta"):
            self.lines.append("    gimeta: ClassVar[GIMeta]")
            body_started = True
        for prop in klass.properties:
            if not _take(prop.py_name):
                continue
            if prop.deprecated:
                self._dep(True, prop.deprecated_version, "    ")
                self.lines.append("    @property")
                self.lines.append(
                    f"    def {prop.py_name}(self) -> {prop.type_expr}: ..."
                )
            else:
                self.lines.append(f"    {prop.py_name}: {prop.type_expr}")
            body_started = True
        # GObject classes are constructed by keyword from their writable
        # properties (Label(label="hi", xalign=0.5)); emit a typed keyword-only
        # __init__ for them, with **kwargs for inherited/unlisted props. Named
        # constructors stay as @classmethods (emitted by the loop below). A
        # hand-written overlay __init__ (in `seen`) wins.
        if klass.is_gobject and "__init__" not in seen:
            self.lines.append(self._gobject_init(klass))
            seen.add("__init__")
            body_started = True
        for ctor in klass.constructors:
            if not _take(_ident(ctor.name)):
                continue
            self._emit_constructor(klass, ctor, seen)
            body_started = True
        # When a signal has a real GIR method backing with the same name,
        # the signal descriptor wins. Mark these in `seen` so the method loop
        # skips them; the signal loop re-emits the name as SignalMethod.
        signal_wins: set[str] = set()
        if self.mode != "gi":
            signal_wins = self._signal_backing_method_names(klass)
            seen |= signal_wins
        # GIR routinely refines a method's signature in a subclass
        # (CheckButton.new_with_label specialises Button.new_with_label,
        # GtkEntry.set_cursor takes different positional args than
        # Widget.set_cursor). override/type-arg/misc are now suppressed
        # file-wide via the file-level directive; no per-line suffix needed.
        for m in klass.methods:
            method_name = _ident(m.name)
            if not _take(method_name):
                continue
            if self._emit_async_overloads(
                callable_map={item.name: item for item in klass.methods},
                fn=m,
                indent="    ",
                instance="self",
            ):
                body_started = True
                continue
            self._dep(m.deprecated, m.deprecated_version, "    ")
            sig = self._signature(m, instance="self")
            self._callable_def("    ", f"def {method_name}{sig}", doc=m.doc)
            body_started = True
        for m in klass.virtual_methods:
            method_name = _ident(m.name)
            if not _take(method_name):
                continue
            self._dep(m.deprecated, m.deprecated_version, "    ")
            sig = self._signature(m, instance="self")
            self._callable_def("    ", f"def {method_name}{sig}", doc=m.doc)
            body_started = True
        for fn in klass.static_functions:
            fn_name = _ident(fn.name)
            if not _take(fn_name):
                continue
            if self._emit_async_overloads(
                callable_map={item.name: item for item in klass.static_functions},
                fn=fn,
                indent="    ",
                instance=None,
                decorators=("staticmethod",),
            ):
                body_started = True
                continue
            self._dep(fn.deprecated, fn.deprecated_version, "    ")
            self.lines.append("    @staticmethod")
            sig = self._signature(fn, instance=None)
            self._callable_def("    ", f"def {fn_name}{sig}", doc=fn.doc)
            body_started = True
        if klass.signals and self._emit_signals(klass, seen, _take, signal_wins):
            body_started = True
        if not body_started:
            self.lines.append("    pass")
        self.lines.append("")

    def _apply_item_type(self, klass: Klass, item: str) -> None:
        """Auto-parameterize an item-typed list model from a declarative spec.

        `item` is a generic TypeVar (e.g. ``"_T"``, recognised by a leading
        underscore) or a concrete element type (e.g. ``"Gtk.StringObject"``).
        The class's ``GObject.Object``-typed members (the items) are rewritten
        to `item`, ``get_item_type`` / the ``item-type`` property become
        ``type[item]``, and the implemented ``Gio.ListModel`` base is
        parameterized. For generic models the wrapped ``Gio.ListModel``
        accessors and the class's own type are parameterized too, so e.g.
        ``FilterListModel.new(model) -> FilterListModel[_T]``.
        """
        generic = item.startswith("_")
        cls = klass.name
        # Within Gio's own stub, ListModel is referenced bare (same namespace);
        # elsewhere it's `Gio.ListModel`.
        listmodel = "ListModel" if self.ns.name == "Gio" else "Gio.ListModel"

        def rewrite(expr: str) -> str:
            out = re.sub(r"\bGObject\.Object\b", item, expr)
            if generic:
                out = re.sub(
                    r"\b(?:Gio\.)?ListModel\b(?!\[)", f"{listmodel}[{item}]", out
                )
                out = re.sub(rf"\b{re.escape(cls)}\b(?!\[)", f"{cls}[{item}]", out)
            return out

        klass.parents = [
            f"{listmodel}[{item}]" if p in ("Gio.ListModel", "ListModel") else p
            for p in klass.parents
        ]
        callables = [
            *klass.methods,
            *klass.virtual_methods,
            *klass.constructors,
            *klass.static_functions,
        ]
        for c in callables:
            if c.name == "get_item_type":
                c.return_expr = f"type[{item}]"
            else:
                c.return_expr = rewrite(c.return_expr)
            c.out_exprs = [rewrite(e) for e in c.out_exprs]
            for p in c.params:
                p.type_expr = rewrite(p.type_expr)
        for prop in klass.properties:
            if prop.name in ("item-type", "item_type"):
                prop.type_expr = f"type[{item}]"
            else:
                prop.type_expr = rewrite(prop.type_expr)

    def _signal_handler_type(self, sig: Signal) -> str:
        # A signal handler is called with the emitting instance first, then the
        # signal's own arguments (trailing connect *args are modelled loosely).
        arg_types = ", ".join(["Self", *(p.type_expr for p in sig.params)])
        return f"Callable[[{arg_types}], {sig.return_expr}]"

    def _emit_signals(
        self,
        klass: Klass,
        seen: set[str],
        take: _Callable[[str], bool],
        signal_wins: set[str] | None = None,
    ) -> bool:
        """Emit a class's signal surface.

        native: each signal is a descriptor attribute — ``_SignalMethod`` for
        an action signal (callable to emit, e.g. ``obj.clicked()``) else
        ``_Signal`` — so ``obj.<signal>.connect(handler)`` is typed. gi
        (pygobject-compat): the legacy string-keyed ``connect``/``emit``
        ``@overload``s. ``do_<signal>`` handlers are emitted in both.
        """
        if self.mode != "gi":
            # Signal-wins-over-method names were pre-seeded into `seen` to
            # suppress method emission; remove them now so the signal loop can
            # emit the descriptor (which calls _take again, re-adding them).
            if signal_wins:
                seen -= signal_wins
            return self._emit_signals_native(klass, seen, take)
        return self._emit_signals_gi(klass, seen, take)

    def _emit_signals_native(
        self, klass: Klass, seen: set[str], take: _Callable[[str], bool]
    ) -> bool:
        emitted = False
        for sig in klass.signals:
            py_name = _ident(sig.name)
            # The signal descriptor is always emitted.  When there is also a
            # same-class GIR method with the same name (e.g. Dialog.response),
            # the method was already excluded by _class pre-seeding `seen` with
            # _signal_method_names before the method emission loop.
            # Interface/ancestor methods with the same name are handled by the
            # same mechanism: if the signal is here, it wins over MRO methods.
            if not take(py_name):
                continue
            # A signal is callable via _SignalMethod only when it has a real
            # GIR method backing with the same name.
            is_callable = py_name in self._signal_backing_method_names(klass)
            # The ``notify`` signal is special: obj.notify("selected")
            # returns a detail-scoped signal for connect/disconnect.
            if sig.name == "notify" and is_callable:
                helper = "DetailedSignal"
            else:
                helper = "SignalMethod" if is_callable else "Signal"
            # Apply per-signal parameter type overrides if declared.
            overridden: list[str] = []
            for i, p in enumerate(sig.params):
                key = (self.ns.name, klass.name, sig.name, i)
                overridden.append(_SIGNAL_PARAM_OVERRIDES.get(key, p.type_expr))
            param_types = ", ".join(overridden)
            prop_conflict = py_name in self._signal_property_conflicts(klass)
            if prop_conflict:
                continue
            # Use Self so subclasses inherit a specialized signal type:
            # `dropdown.notify("selected").connect(cb)` where cb: (DropDown, ...) -> None
            # rather than cb: (Object, ...) -> None.
            self.lines.append(
                f"    {py_name}: {helper}[Self, [{param_types}], {sig.return_expr}]"
            )
            emitted = True
        for sig in klass.signals:
            do_name = "do_" + _ident(sig.name)
            if not take(do_name):
                continue
            params = "".join(f", {p.name}: {p.type_expr}" for p in sig.params)
            self.lines.append(
                f"    def {do_name}(self{params}) -> {sig.return_expr}: ..."
            )
            emitted = True
        return emitted

    def _emit_signals_gi(
        self, klass: Klass, seen: set[str], take: _Callable[[str], bool]
    ) -> bool:
        emitted = False
        for cname in ("connect", "connect_after"):
            if cname in seen:
                continue
            for sig in klass.signals:
                handler = self._signal_handler_type(sig)
                self.lines.append("    @overload")
                self.lines.append(
                    f'    def {cname}(self, signal: Literal["{sig.name}"], '
                    f"handler: {handler}, *args: Any) -> int: ..."
                )
            self.lines.append("    @overload")
            self.lines.append(
                f"    def {cname}(self, signal: str, "
                f"handler: Callable[..., Any], *args: Any) -> int: ..."
            )
            seen.add(cname)
            emitted = True
        if "emit" not in seen:
            for sig in klass.signals:
                params = "".join(f", {p.name}: {p.type_expr}" for p in sig.params)
                self.lines.append("    @overload")
                self.lines.append(
                    f'    def emit(self, signal: Literal["{sig.name}"]{params}) '
                    f"-> {sig.return_expr}: ..."
                )
            self.lines.append("    @overload")
            self.lines.append("    def emit(self, signal: str, *args: Any) -> Any: ...")
            seen.add("emit")
            emitted = True
        for sig in klass.signals:
            do_name = "do_" + _ident(sig.name)
            if not take(do_name):
                continue
            params = "".join(f", {p.name}: {p.type_expr}" for p in sig.params)
            self.lines.append(
                f"    def {do_name}(self{params}) -> {sig.return_expr}: ..."
            )
            emitted = True
        return emitted

    def _ns_overlay(self) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        # Harvested (runtime @overlay.*) first, then the hand-written native
        # TOML (C-slot surface) which may add to / override it, then mode.
        for source in (_HARVESTED_OVERLAYS, _NATIVE_OVERLAYS, self.mode_overlays):
            ns = source.get("ns", {}).get(self.ns.name, {})
            if not isinstance(ns, dict):
                continue
            for key, value in ns.items():
                if key == "classes" and isinstance(value, dict):
                    classes = merged.setdefault("classes", {})
                    for cname, cvalue in value.items():
                        if isinstance(cvalue, dict) and isinstance(
                            classes.get(cname), dict
                        ):
                            classes[cname] = _merge_class_overlay(
                                classes[cname], cvalue
                            )
                        else:
                            classes[cname] = cvalue
                elif key == "prelude":
                    existing = merged.get("prelude")
                    if existing and value:
                        merged["prelude"] = (
                            f"{existing.rstrip()}\n\n{str(value).rstrip()}"
                        )
                    else:
                        merged[key] = value
                else:
                    merged[key] = value
        return merged

    def _overlay_body_lines_with_docs(self, body: str, klass: Klass) -> list[str]:
        docs: dict[str, str] = {m.name: m.doc for m in klass.methods if m.doc}
        docs.update({m.name: m.doc for m in klass.virtual_methods if m.doc})
        docs.update({c.name: c.doc for c in klass.constructors if c.doc})
        if not docs:
            return body.rstrip().splitlines()

        output: list[str] = []
        pending_decorators: list[str] = []
        lines = body.rstrip().splitlines()
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith("@"):
                pending_decorators.append(line)
                continue
            match = re.match(
                r"(?P<indent>\s*)(?:async\s+)?def\s+(?P<name>\w+)\(.*\)\s*->\s*[^:]+:\s*\.\.\.\s*$",
                line,
            )
            if match and (doc := docs.get(match.group("name"))):
                output.extend(pending_decorators)
                pending_decorators = []
                output.append(line.replace(": ...", ":"))
                self._append_docstring_lines(
                    output, match.group("indent") + "    ", doc
                )
                continue
            output.extend(pending_decorators)
            pending_decorators = []
            output.append(line)
        output.extend(pending_decorators)
        return output

    def _callable_def(
        self,
        indent: str,
        header: str,
        *,
        suffix: str = "",
        doc: str | None = None,
    ) -> None:
        if not doc:
            self.lines.append(f"{indent}{header}: ...{suffix}")
            return
        self.lines.append(f"{indent}{header}:{suffix}")
        self._docstring(indent + "    ", doc)

    def _docstring(self, indent: str, doc: str) -> None:
        self._append_docstring_lines(self.lines, indent, doc)

    def _append_docstring_lines(self, output: list[str], indent: str, doc: str) -> None:
        safe = doc.replace("\\", "\\\\").replace('"""', r"\"\"\"")
        output.append(f'{indent}"""')
        for line in safe.splitlines():
            output.append(f"{indent}{line}".rstrip())
        output.append(f'{indent}"""')

    def _signature(
        self, fn: Callable, *, instance: str | None, return_override: str | None = None
    ) -> str:
        return render_signature(fn, instance=instance, return_override=return_override)

    def _gobject_init(self, klass: Klass) -> str:
        """Typed keyword-only __init__ for a GObject from its writable props.

        ``def __init__(self, *, prop: T = ..., ..., **kwargs: Any) -> None``.
        Known properties are type-checked; the trailing ``**kwargs`` keeps
        inherited and unlisted properties usable (mypy exempts __init__ from
        override checks, so this composes across subclasses)."""
        params: list[str] = []
        emitted: set[str] = set()
        for prop in klass.properties:
            if not prop.writable or prop.py_name in emitted:
                continue
            emitted.add(prop.py_name)
            params.append(
                f"{prop.py_name}: {_widen_glib_bytes_input(prop.type_expr)} = ..."
            )
        if not params:
            return "    def __init__(self, **kwargs: Any) -> None: ..."
        return (
            f"    def __init__(self, *, {', '.join(params)}, "
            "**kwargs: Any) -> None: ..."
        )

    def _emit_constructor(
        self, klass: Klass, ctor: Callable, seen: set[str] | None = None
    ) -> None:
        self._dep(ctor.deprecated, ctor.deprecated_version, "    ")
        ctor_map = {item.name: item for item in klass.constructors}
        # Use ``Self`` for the classmethod return so subclasses inherit a
        # override/type-arg/misc are suppressed file-wide; no per-line suffix.
        if ctor.name == "new":
            # GObject __init__ is the typed keyword-only form (emitted by
            # _gobject_init); a GObject ``new`` is only the @classmethod. Plain
            # records keep __init__ derived from ``new``'s signature.
            if not klass.is_gobject and (seen is None or "__init__" not in seen):
                sig = self._signature(ctor, instance="self", return_override="None")
                self._callable_def("    ", f"def __init__{sig}", doc=ctor.doc)
                if seen is not None:
                    seen.add("__init__")
            # GObject new() constructors legitimately vary their required params
            # across the hierarchy — subclasses routinely add or change params.
            # Rather than fight Liskov here, emit a permissive *args/**kwargs
            # signature for new() on every GObject class; the specific params
            # are available via the typed __init__ (keyword-only GObject ctor).
            self.lines.append("    @classmethod")
            if klass.is_gobject:
                self.lines.append(
                    "    def new(cls, *args: Any, **kwargs: Any) -> Self: ..."
                )
            else:
                sig = self._signature(ctor, instance="cls", return_override="Self")
                self._callable_def("    ", f"def new{sig}", doc=ctor.doc)
        else:
            if self._emit_async_overloads(
                callable_map=ctor_map,
                fn=ctor,
                indent="    ",
                instance="cls",
                return_override="Self",
                decorators=("classmethod",),
            ):
                return
            self.lines.append("    @classmethod")
            sig = self._signature(ctor, instance="cls", return_override="Self")
            self._callable_def("    ", f"def {_ident(ctor.name)}{sig}", doc=ctor.doc)

    def _callable_return_expr(
        self, fn: Callable, *, return_override: str | None = None
    ) -> str:
        ret = return_override if return_override is not None else fn.return_expr
        if not fn.out_exprs:
            return ret
        base_parts = [] if ret == "None" else [ret]
        tuple_parts = base_parts + fn.out_exprs
        if len(tuple_parts) == 1:
            return tuple_parts[0]
        return f"tuple[{', '.join(tuple_parts)}]"

    def _async_finish_name(
        self, callable_map: dict[str, Callable], async_name: str
    ) -> str | None:
        if not async_name.endswith("_async"):
            return None
        base = async_name[: -len("_async")]
        direct = f"{base}_finish"
        if direct in callable_map:
            return direct
        best = ""
        finish_name: str | None = None
        for candidate in callable_map:
            if not candidate.endswith("_finish"):
                continue
            stem = candidate[: -len("_finish")]
            if (base == stem or base.startswith(f"{stem}_")) and len(stem) > len(best):
                best = stem
                finish_name = candidate
        return finish_name

    def _strip_none(self, type_expr: str) -> str:
        if type_expr.endswith(" | None"):
            return type_expr[: -len(" | None")]
        return type_expr

    def _signature_from_params(
        self,
        params: list[Param],
        *,
        instance: str | None,
        return_expr: str,
    ) -> str:
        parts: list[str] = []
        if instance:
            parts.append(instance)
        for param in params:
            part = f"{param.name}: {param.type_expr}"
            if param.has_default:
                part += " = ..."
            parts.append(part)
        return f"({', '.join(parts)}) -> {return_expr}"

    def _emit_async_overloads(
        self,
        *,
        callable_map: dict[str, Callable],
        fn: Callable,
        indent: str,
        instance: str | None,
        return_override: str | None = None,
        decorators: tuple[str, ...] = (),
    ) -> bool:
        if self.mode == "gi" or not fn.name.endswith("_async") or not fn.params:
            return False
        callback = fn.params[-1]
        if callback.name != "callback":
            return False
        finish_name = self._async_finish_name(callable_map, fn.name)
        if finish_name is None:
            return False
        finish = callable_map[finish_name]
        await_return = self._callable_return_expr(
            finish, return_override=return_override
        )
        await_params = [
            *fn.params[:-1],
            Param("callback", "None", "in", True, True),
        ]
        callback_params = [
            *fn.params[:-1],
            Param(
                "callback",
                self._strip_none(callback.type_expr),
                "in",
                False,
                True,
            ),
        ]
        self._dep(fn.deprecated, fn.deprecated_version, indent)
        self.lines.append(f"{indent}@overload")
        for decorator in decorators:
            self.lines.append(f"{indent}@{decorator}")
        await_sig = self._signature_from_params(
            await_params,
            instance=instance,
            return_expr=f"Awaitable[{await_return}]",
        )
        self._callable_def(indent, f"def {fn.name}{await_sig}", doc=fn.doc)
        self.lines.append(f"{indent}@overload")
        for decorator in decorators:
            self.lines.append(f"{indent}@{decorator}")
        callback_sig = self._signature_from_params(
            callback_params,
            instance=instance,
            return_expr="None",
        )
        self._callable_def(indent, f"def {fn.name}{callback_sig}", doc=fn.doc)
        return True


# ---------------------------------------------------------------------------
# Hand-written augmentations for GObject.Object — the PyGObject signal /
# property API isn't visible in the .gir but is essential for user code.
# ---------------------------------------------------------------------------

# Native overlays — declarative blocks for surface installed via C type
# slots. Loaded from ginext_stubgen/native_overlays.toml so the generator
# stays free of hardcoded Python source.


def _load_native_overlays() -> dict[str, Any]:
    path = Path(__file__).resolve().parent / "native_overlays.toml"
    if not path.is_file():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


_NATIVE_OVERLAYS: dict[str, Any] = _load_native_overlays()


def _body_member_names(body: str) -> set[str]:
    """Names defined by a stub-body text block (``def x``, ``x: T``, ``class X``)."""
    names: set[str] = set()
    for line in body.splitlines():
        m = re.match(r"\s*(?:async\s+)?def\s+(\w+)\b", line) or re.match(
            r"\s*(?:class\s+)?(\w+)\s*[:(]", line
        )
        if m:
            names.add(m.group(1))
    return names


def _drop_body_members(body: str, names: set[str]) -> str:
    """Drop member blocks (a def/attr line plus its leading decorators) whose
    name is in ``names`` — used so a higher-precedence body wins per member."""
    out: list[str] = []
    pending: list[str] = []
    for line in body.splitlines():
        if line.strip().startswith("@"):
            pending.append(line)
            continue
        m = re.match(r"\s*(?:async\s+)?def\s+(\w+)\b", line) or re.match(
            r"\s*(\w+)\s*[:(]", line
        )
        if m and m.group(1) in names:
            pending = []
            continue
        out.extend(pending)
        pending = []
        out.append(line)
    out.extend(pending)
    return "\n".join(out)


_foreign_enum_cache: dict[str, frozenset[str]] = {}


def _foreign_enum_like(ns_name: str) -> frozenset[str]:
    """Return the set of enum/bitfield names in a foreign namespace.

    Lazily loads the foreign GIR on first call and caches the result.
    Returns an empty set if the GIR is not available.
    """
    if ns_name in _foreign_enum_cache:
        return _foreign_enum_cache[ns_name]
    # Find the GIR for the foreign namespace using default version resolution.
    gir = None
    for ver_hint in ("2.0", "4.0", "1.0", "0.0", "3.0"):
        candidate = find_gir(ns_name, ver_hint)
        if candidate is not None:
            gir = candidate
            break
    names: set[str] = set()
    if gir is not None:
        try:
            root = ET.parse(gir).getroot()
            ns_el = root.find("gi:namespace", NS)
            if ns_el is not None:
                for child in ns_el:
                    if child.get("introspectable") == "0":
                        continue
                    name = child.get("name")
                    if name and child.tag in (
                        "{http://www.gtk.org/introspection/core/1.0}bitfield",
                        "{http://www.gtk.org/introspection/core/1.0}enumeration",
                    ):
                        names.add(name)
        except (OSError, ET.ParseError):
            pass
    result = frozenset(names)
    _foreign_enum_cache[ns_name] = result
    return result


def _merge_class_overlay(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Merge two per-class overlay dicts. ``b`` (the hand-written native TOML)
    wins per member; ``a`` (harvested runtime overlays) fills the remainder.
    Union list fields (``reserves``/``extra_bases``)."""
    out = {**a, **b}
    a_body, b_body = a.get("body"), b.get("body")
    if isinstance(a_body, str) and isinstance(b_body, str):
        kept = _drop_body_members(a_body, _body_member_names(b_body))
        out["body"] = f"{b_body.rstrip()}\n{kept.strip()}".rstrip()
    for field_name in ("reserves", "extra_bases"):
        a_list = a.get(field_name) if isinstance(a.get(field_name), list) else []
        b_list = b.get(field_name) if isinstance(b.get(field_name), list) else []
        if a_list or b_list:
            seen: list[object] = []
            for item in (list(a_list) if isinstance(a_list, list) else []) + (
                list(b_list) if isinstance(b_list, list) else []
            ):
                if item not in seen:
                    seen.append(item)
            out[field_name] = seen
    return out


def _load_harvested_overlays() -> dict[str, Any]:
    # Statically harvest the runtime @overlay.* declarations from the repo's
    # _overlays/*.py and present them in the same shape as _NATIVE_OVERLAYS.
    repo_root = Path(__file__).resolve().parents[4]
    try:
        return {"ns": harvest_overlays([repo_root])}
    except OSError:
        return {}


_HARVESTED_OVERLAYS: dict[str, Any] = _load_harvested_overlays()


def _load_mode_overlay_file(filename: str) -> dict[str, Any]:
    path = Path(__file__).resolve().parent / filename
    if not path.is_file():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


_NATIVE_MODE_OVERLAYS: dict[str, Any] = _load_mode_overlay_file(
    "native_mode_overlays.toml"
)


def _mode_overlays(mode: Mode) -> dict[str, Any]:
    if mode == "native":
        return _NATIVE_MODE_OVERLAYS
    return {}


# ---------------------------------------------------------------------------
# Top-level entry
# ---------------------------------------------------------------------------


def _apply_toml_overlay(ns: Namespace, overlay: dict[str, Any]) -> None:
    """Apply transforms from src/ginext/_overlays/<NS>-<v>.toml to a parsed namespace.

    Supported entry kinds:

    * ``kind = "alias"`` with ``target = "X"`` — emits ``NAME = X`` at the top
      of the .pyi. Used for legacy compat names like
      ``GLib.USER_DIRECTORY_DESKTOP``.
    * ``kind = "internal"`` — drop the GIR-derived emission. Internal types
      (``GObject.Type``, ``GObject.Signal``, ``GLib.Boxed``) are wired up
      by the runtime and stubbed by ``native_overlays.toml`` if needed.
    * ``kind = "class" [Class.props.X] getter = "Y"`` — add ``X`` as a
      property to ``Class``, inheriting the type from method ``Y``'s return.
    * ``kind = "class" [Class.methods.X] from_function = "Y"`` — bind
      method ``X`` to top-level function ``Y``'s signature.
    * Top-level entry with ``shadows = "X"`` — applied implicitly through
      GIR's own ``shadowed-by`` attribute. The TOML form is informational
      until/unless we model the ``params = [...]`` rewrites below.
    """
    if not overlay:
        return

    by_class: dict[str, Klass] = {kl.name: kl for kl in ns.classes}
    funcs_by_name: dict[str, Callable] = {fn.name: fn for fn in ns.functions}
    methods_index: dict[tuple[str, str], Callable] = {
        (kl.name, m.name): m for kl in ns.classes for m in kl.methods
    }

    def _resolve_type_from_callable(c: Callable) -> str:
        return c.return_expr

    for key, entry in overlay.items():
        if not isinstance(entry, dict):
            # Top-level scalars like ``version = "2.0"``.
            continue
        kind = entry.get("kind")
        if kind == "alias":
            target = entry.get("target")
            if target:
                ns.aliases.append(Alias(name=key, target_expr=target))
        elif kind == "internal":
            # Drop the GIR-derived alias/class for this name — the type is
            # registered as a goi internal and ought to be hand-stubbed via
            # native_overlays.toml.
            ns.aliases = [a for a in ns.aliases if a.name != key]
            ns.classes = [c for c in ns.classes if c.name != key]
        elif kind == "class":
            klass = by_class.get(key)
            if klass is None:
                # GIR didn't define this class; can't add props/methods.
                continue
            props_section = entry.get("props", {})
            if isinstance(props_section, dict):
                for prop_name, prop_cfg in props_section.items():
                    if not isinstance(prop_cfg, dict):
                        continue
                    getter = prop_cfg.get("getter")
                    type_expr = "Any"
                    if isinstance(getter, str):
                        m = methods_index.get((klass.name, getter))
                        if m is not None:
                            type_expr = _resolve_type_from_callable(m)
                    klass.properties.append(
                        Property(
                            name=prop_name,
                            py_name=_ident(prop_name),
                            type_expr=type_expr,
                        )
                    )
            methods_section = entry.get("methods", {})
            if isinstance(methods_section, dict):
                for method_name, method_cfg in methods_section.items():
                    if not isinstance(method_cfg, dict):
                        continue
                    from_function = method_cfg.get("from_function")
                    if isinstance(from_function, str):
                        fn = funcs_by_name.get(from_function)
                        if fn is not None:
                            # Strip the leading instance param: the function
                            # took the object as its first arg, the method
                            # form has ``self`` instead.
                            method = Callable(
                                name=method_name,
                                params=list(fn.params[1:]) if fn.params else [],
                                return_expr=fn.return_expr,
                                out_exprs=list(fn.out_exprs),
                                is_throws=fn.is_throws,
                            )
                            klass.methods.append(method)


def load_overlay_toml(namespace: str, version: str) -> dict[str, Any]:
    """Locate ``src/ginext/_overlays/<NS>-<version>.toml`` and load it.

    These declarative TOML overlays are the supported way to augment a
    namespace's stub (add an alias, drop an internal type, add a property from
    a getter, bind a method to a function); see ``_apply_toml_overlay``. Walks
    upward from this file's parent so the generator works when invoked via
    ``python -m`` from any cwd. Returns an empty dict if no overlay exists.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = (
            parent / "src" / "ginext" / "_overlays" / f"{namespace}-{version}.toml"
        )
        if candidate.is_file():
            with candidate.open("rb") as fh:
                return tomllib.load(fh)
    return {}


def build_namespace(
    gir_path: Path,
    *,
    doc_format: Literal["rst", "raw"] = "rst",
    cache_dir: Path | None = None,
) -> tuple[Namespace, Parser]:
    """Parse a .gir into the overlay-applied Namespace model.

    Shared by ``generate`` (.pyi) and the doc generator so both consume an
    identical model — Python signatures, docs, and overlays cannot drift.
    Returns ``(namespace, parser)``; the parser exposes the doc cross-reference
    maps (``_doc_identifiers`` / ``_doc_types`` / ``_doc_constants``).

    When *cache_dir* is given, the parsed ``Namespace`` is pickled there under
    ``<Name>-<version>.pkl`` keyed on the GIR mtime + overlay hash.  On a cache
    hit the ``Parser`` slot is ``None`` (callers that need the parser, e.g. the
    doc generator, bypass the cache by passing ``cache_dir=None``).
    """
    import hashlib
    import json
    import os
    import pickle

    overlay: dict[str, Any] = {}
    parser = Parser(gir_path, overlay=overlay, doc_format=doc_format)
    # Re-resolve the overlay TOML now that we know the namespace name +
    # version from the GIR header. Re-init the parser with the overlay so
    # parsing can react to it (e.g. skipping kind="internal" entries).
    ns_name_peek = parser.ns_name
    ns_version_peek = parser.ns_version
    overlay = load_overlay_toml(ns_name_peek, ns_version_peek)

    # --- pickle cache ---
    if cache_dir is not None and os.environ.get("GINEXT_STUBGEN_NO_CACHE") != "1":
        overlay_hash = hashlib.sha256(
            json.dumps(overlay, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]
        cache_key = (
            str(gir_path.resolve()),
            gir_path.stat().st_mtime_ns,
            overlay_hash,
        )
        cache_file = cache_dir / f"{ns_name_peek}-{ns_version_peek}.pkl"
        try:
            if cache_file.exists():
                stored_key, cached_ns = pickle.loads(cache_file.read_bytes())
                if stored_key == cache_key:
                    return cached_ns, None  # type: ignore[return-value]
        except Exception:
            pass  # corrupt or incompatible cache — fall through to full parse
    else:
        cache_key = None
        cache_file = None

    parser = Parser(gir_path, overlay=overlay, doc_format=doc_format)
    ns = parser.parse()
    _apply_toml_overlay(ns, overlay)
    # PyGObject historically merges a handful of small companion namespaces
    # into their parent: ``GLibUnix.signal_add`` is exposed as
    # ``GLib.unix_signal_add``, etc. Pull those in when generating the
    # parent so user code that uses the merged names typechecks.
    if ns.name == "GLib":
        unix_gir = find_gir("GLibUnix", "2.0")
        if unix_gir is not None:
            unix_ns = Parser(unix_gir, doc_format=doc_format).parse()

            # GLibUnix types reference ``GLib.X`` because they live in a
            # separate namespace. After merging into GLib those become
            # self-references and need to lose the qualifier.
            def _unqualify(expr: str) -> str:
                return expr.replace("GLib.", "")

            for fn in unix_ns.functions:
                fn.name = "unix_" + fn.name
                fn.return_expr = _unqualify(fn.return_expr)
                for p in fn.params:
                    p.type_expr = _unqualify(p.type_expr)
                fn.out_exprs = [_unqualify(e) for e in fn.out_exprs]
                ns.functions.append(fn)
            # Pull in callbacks too — ``unix_fd_add_full`` references
            # ``FDSourceFunc`` which lives in the GLibUnix namespace.
            for cb in unix_ns.callbacks:
                cb.return_expr = _unqualify(cb.return_expr)
                for p in cb.params:
                    p.type_expr = _unqualify(p.type_expr)
                ns.callbacks.append(cb)
            ns.foreign_namespaces.update(unix_ns.foreign_namespaces - {"GLib"})

    # --- write cache ---
    if cache_dir is not None and cache_key is not None and cache_file is not None:
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file.write_bytes(pickle.dumps((cache_key, ns), protocol=5))
        except OSError:
            pass  # silently skip caching on any OS error

    return ns, parser


def generate(
    gir_path: Path,
    *,
    mode: Mode = "native",
    cache_dir: Path | None = None,
) -> tuple[str, str]:
    """Parse a single .gir file and return (namespace, .pyi text)."""
    ns, _parser = build_namespace(gir_path, cache_dir=cache_dir)
    text = Emitter(ns, mode=mode).emit()
    return ns.name, text


def gir_search_dirs() -> list[Path]:
    """Default search path for system .gir files. Mirrors find_system_gir."""
    import os
    import shutil
    import subprocess

    dirs: list[Path] = []
    env_dir = os.environ.get("GOI_GIR_DIR")
    if env_dir:
        dirs.append(Path(env_dir))
    dirs.append(Path("/usr/share/gir-1.0"))
    # Debian splits some .gir files into /usr/lib/<multiarch>/gir-1.0/.
    for sub in Path("/usr/lib").glob("*/gir-1.0"):
        if sub.is_dir():
            dirs.append(sub)
    pkg_config = shutil.which("pkg-config")
    if pkg_config:
        try:
            out = subprocess.check_output(
                [pkg_config, "--variable=girdir", "gobject-introspection-1.0"],
                text=True,
            ).strip()
            if out:
                dirs.append(Path(out))
        except (subprocess.CalledProcessError, OSError):
            pass
        # The base GObject/Gio/GLib GIRs are shipped with glib, not with
        # gobject-introspection. On Homebrew (macOS) they live under glib's
        # own datadir rather than /usr/share, so resolve it via pkg-config.
        for pkg in ("gio-2.0", "gobject-2.0", "glib-2.0"):
            try:
                datadir = subprocess.check_output(
                    [pkg_config, "--variable=datadir", pkg],
                    text=True,
                ).strip()
            except (subprocess.CalledProcessError, OSError):
                continue
            if datadir:
                dirs.append(Path(datadir) / "gir-1.0")
    # On Homebrew (macOS) every introspected package symlinks its GIR into the
    # shared prefix, so a single $(brew --prefix)/share/gir-1.0 covers the whole
    # toolkit stack (Gtk, Gdk, Pango, ...) that the per-package datadirs above
    # would otherwise miss.
    brew = shutil.which("brew")
    if brew:
        try:
            prefix = subprocess.check_output([brew, "--prefix"], text=True).strip()
        except (subprocess.CalledProcessError, OSError):
            prefix = ""
        if prefix:
            dirs.append(Path(prefix) / "share" / "gir-1.0")
    # Include the in-repo test-typelib build directory if present. These GIRs
    # are not installed system-wide; they live under build/<variant>/packages/typelib.
    _add_gi_tests_gir_dirs(dirs)
    seen: set[Path] = set()
    deduped: list[Path] = []
    for d in dirs:
        if d in seen or not d.is_dir():
            continue
        seen.add(d)
        deduped.append(d)
    return deduped


def _add_gi_tests_gir_dirs(dirs: list[Path]) -> None:
    """Scan build/ for packages/typelib GIR output directories."""
    # Walk up from this file to find the repo root (contains a build/ dir).
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        build = ancestor / "build"
        if not build.is_dir():
            continue
        # Look for any build variant that has the test GIRs.
        sentinel = "GIMarshallingTests-1.0.gir"
        for variant in sorted(build.iterdir()):
            candidate = variant / "packages" / "typelib"
            if (candidate / sentinel).is_file():
                dirs.append(candidate)
        break


def find_gir(name: str, version: str) -> Path | None:
    filename = f"{name}-{version}.gir"
    for d in gir_search_dirs():
        candidate = d / filename
        if candidate.is_file():
            return candidate
    return None
