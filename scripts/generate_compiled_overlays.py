#!/usr/bin/env python3

"""Compile goi overlay TOML specs into a single static C table.

The runtime / JIT consumes the generated tables directly — there is no
parsing or schema interpretation at runtime. Adding a new behavior means
extending this generator and the matching tag enum in overlays.h, not
adding a new C dispatch function.
"""

import pathlib
import sys
import tomllib
from typing import cast


PARAM_KINDS = {
    "required": "GOI_OVERLAY_PARAM_REQUIRED",
    "variadic": "GOI_OVERLAY_PARAM_VARIADIC",
    "keyword": "GOI_OVERLAY_PARAM_KEYWORD",
}

CALL_KINDS = {
    "identity": "GOI_OVERLAY_CALL_IDENTITY",
    "pack": "GOI_OVERLAY_CALL_PACK",
    "value_none": "GOI_OVERLAY_CALL_VALUE_NONE",
    "value_int": "GOI_OVERLAY_CALL_VALUE_INT",
    "value_bool": "GOI_OVERLAY_CALL_VALUE_BOOL",
    "value_string": "GOI_OVERLAY_CALL_VALUE_STRING",
    "value_tuple": "GOI_OVERLAY_CALL_VALUE_TUPLE",
}

TUPLE_ITEM_KINDS = {
    "int": "GOI_OVERLAY_TUPLE_ITEM_INT",
    "bool": "GOI_OVERLAY_TUPLE_ITEM_BOOL",
    "string": "GOI_OVERLAY_TUPLE_ITEM_STRING",
    "none": "GOI_OVERLAY_TUPLE_ITEM_NONE",
}

RETURN_KINDS = {
    "passthrough": "GOI_OVERLAY_RETURN_PASSTHROUGH",
    "value_none": "GOI_OVERLAY_RETURN_VALUE_NONE",
    "value_int": "GOI_OVERLAY_RETURN_VALUE_INT",
    "value_bool": "GOI_OVERLAY_RETURN_VALUE_BOOL",
    "value_string": "GOI_OVERLAY_RETURN_VALUE_STRING",
    "from_param": "GOI_OVERLAY_RETURN_FROM_PARAM",
    "list_from_param": "GOI_OVERLAY_RETURN_LIST_FROM_PARAM",
}

ENTRY_KINDS = {
    "function": "GOI_OVERLAY_KIND_FUNCTION",
    "internal": "GOI_OVERLAY_KIND_INTERNAL",
    "synthetic": "GOI_OVERLAY_KIND_SYNTHETIC",
    "alias": "GOI_OVERLAY_KIND_ALIAS",
}

# Top-level entries with this kind describe a *class* (not a callable).
# They never appear in the function entry table; they go into the
# class_entries table consumed by goi_build_object_class.
CLASS_KIND = "class"
# Tagged-union boxed type (e.g. GdkEvent). Shares the class entry
# table; the runtime installs a generic dispatcher __getattr__ that
# routes attribute access through the union-arm member named by the
# discriminator enum value.
BOXED_UNION_KIND = "boxed_union"


def c_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def c_string_or_null(value: str | None) -> str:
    return "NULL" if value is None else c_string(value)


def c_int(value: int) -> str:
    # TOML integers are arbitrary precision; clamp to long long range.
    return f"{int(value)}LL"


def c_bool(value: bool | int) -> str:
    return "1" if bool(value) else "0"


def ident(value: str) -> str:
    return value.replace("-", "_").replace(".", "_")


DEFAULT_KIND_NONE = "GOI_OVERLAY_DEFAULT_NONE"
DEFAULT_KIND_ATTR = "GOI_OVERLAY_DEFAULT_NAMESPACE_ATTR"
DEFAULT_KIND_INT = "GOI_OVERLAY_DEFAULT_INT"
DEFAULT_KIND_BOOL = "GOI_OVERLAY_DEFAULT_BOOL"


def classify_default(default: object) -> tuple[str, str | None, int, int]:
    """Map a TOML default value to (default_kind, attr_string, int_val, bool_val)."""
    if default is None:
        return DEFAULT_KIND_NONE, None, 0, 0
    if isinstance(default, bool):
        return DEFAULT_KIND_BOOL, None, 0, 1 if default else 0
    if isinstance(default, int):
        return DEFAULT_KIND_INT, None, int(default), 0
    if isinstance(default, str):
        return DEFAULT_KIND_ATTR, default, 0, 0
    raise ValueError(f"unsupported default value: {default!r}")


def parse_param(entry: dict[str, object]) -> tuple[str, str, str, str | None, int, int]:
    """Return (name, kind, default_kind, default_attr, default_int, default_bool)."""
    if len(entry) != 1:
        raise ValueError(f"param entries must contain exactly one key: {entry!r}")
    name, value = next(iter(entry.items()))
    if isinstance(value, str):
        return name, PARAM_KINDS[value], DEFAULT_KIND_NONE, None, 0, 0
    if isinstance(value, dict):
        kind = PARAM_KINDS[cast("str", value["kind"])]
        dk, attr, ival, bval = classify_default(value.get("default"))
        return name, kind, dk, attr, ival, bval
    raise ValueError(f"unsupported param value for {name!r}: {value!r}")


def emit_param_row(entry: dict[str, object]) -> str:
    name, kind, dk, attr, ival, bval = parse_param(entry)
    return (
        f"    {{ {c_string(name)}, {kind}, {dk}, "
        f"{c_string_or_null(attr)}, {c_int(ival)}, {c_bool(bval)} }},"
    )


# Each call-spec turns into a row matching GoiOverlayCallSpec:
# (name, kind, from_name, value_name, value_int, value_bool, value_string,
#  tuple_items_list).  tuple_items_list is None for non-tuple kinds; otherwise
# a list of (kind_enum, ival, bval, sval) describing each tuple element so the
# generator can emit a static GoiOverlayTupleItem[] alongside the spec.
def _classify_tuple_item(v: object) -> tuple[str, int, bool, str | None]:
    if v is None or v == "none":
        return (TUPLE_ITEM_KINDS["none"], 0, False, None)
    if isinstance(v, bool):
        return (TUPLE_ITEM_KINDS["bool"], 0, v, None)
    if isinstance(v, int):
        return (TUPLE_ITEM_KINDS["int"], v, False, None)
    if isinstance(v, str):
        return (TUPLE_ITEM_KINDS["string"], 0, False, v)
    raise ValueError(f"unsupported tuple item: {v!r}")


def parse_call(
    name: str, value: object
) -> tuple[
    str,
    str,
    str | None,
    str | None,
    int,
    bool,
    str | None,
    list[tuple[str, int, bool, str | None]] | None,
]:
    if isinstance(value, str):
        # Shorthand: `arg = "none"` → None / NULL pointer.
        if value == "none":
            return (name, CALL_KINDS["value_none"], None, "none", 0, False, None, None)
        # `arg = "param_name"` → identity from param.
        return (name, CALL_KINDS["identity"], value, None, 0, False, None, None)

    if not isinstance(value, dict):
        raise ValueError(f"unsupported call value for {name!r}: {value!r}")

    if value.get("pack"):
        return (
            name,
            CALL_KINDS["pack"],
            cast("str", value["from"]),
            None,
            0,
            False,
            None,
            None,
        )

    if "tuple" in value:
        items: object = value["tuple"]
        if not isinstance(items, list):
            raise ValueError(f"`tuple` must be a list for {name!r}: {items!r}")
        return (
            name,
            CALL_KINDS["value_tuple"],
            None,
            None,
            0,
            False,
            None,
            [_classify_tuple_item(it) for it in items],
        )

    if "value" in value:
        v = value["value"]
        # Backward-compat: { value = "none" } → None / NULL.
        if v == "none":
            return (name, CALL_KINDS["value_none"], None, "none", 0, False, None, None)
        if isinstance(v, bool):
            return (name, CALL_KINDS["value_bool"], None, None, 0, v, None, None)
        if isinstance(v, int):
            return (name, CALL_KINDS["value_int"], None, None, v, False, None, None)
        if isinstance(v, str):
            return (name, CALL_KINDS["value_string"], None, None, 0, False, v, None)
        raise ValueError(f"unsupported literal value for {name!r}: {v!r}")

    # Default: identity. `from` defaults to the target arg's own name.
    return (
        name,
        CALL_KINDS["identity"],
        cast("str", value.get("from", name)),
        None,
        0,
        False,
        None,
        None,
    )


def parse_return(value: object) -> tuple[str, str | None, int, bool, str | None]:
    """Returns (kind, from_name, value_int, value_bool, value_string)."""
    if value is None:
        return (RETURN_KINDS["passthrough"], None, 0, False, None)
    if isinstance(value, str):
        if value == "none":
            return (RETURN_KINDS["value_none"], None, 0, False, None)
        raise ValueError(f"unsupported `return` shorthand: {value!r}")
    if not isinstance(value, dict):
        raise ValueError(f"unsupported `return` form: {value!r}")
    if "list_from" in value:
        return (
            RETURN_KINDS["list_from_param"],
            cast("str", value["list_from"]),
            0,
            False,
            None,
        )
    if "from" in value:
        return (RETURN_KINDS["from_param"], cast("str", value["from"]), 0, False, None)
    if "value" in value:
        v = value["value"]
        if v == "none":
            return (RETURN_KINDS["value_none"], None, 0, False, None)
        if isinstance(v, bool):
            return (RETURN_KINDS["value_bool"], None, 0, v, None)
        if isinstance(v, int):
            return (RETURN_KINDS["value_int"], None, v, False, None)
        if isinstance(v, str):
            return (RETURN_KINDS["value_string"], None, 0, False, v)
        raise ValueError(f"unsupported `return.value` literal: {v!r}")
    raise ValueError(f"`return` must specify `value` or `from`: {value!r}")


def main() -> int:
    output = pathlib.Path(sys.argv[1])
    inputs = [pathlib.Path(p) for p in sys.argv[2:]]

    lines: list[str] = []
    lines.append('#include "runtime/overlays.h"')
    lines.append("#include <string.h>")
    lines.append("")

    namespace_rows: list[str] = []

    for path in inputs:
        spec = tomllib.loads(path.read_text())
        namespace, version = path.stem.rsplit("-", 1)
        ns_id = ident(path.stem)

        # `[__namespace__]` is a reserved stanza that drives the
        # first-access hook (require list + functions to call). Not
        # an entry — pulled out before the entry split.
        ns_meta = spec.pop("__namespace__", None)

        # Split top-level entries: function-style (callable wrappers) vs
        # class-style (per-class prop accessors). Sort each set so the
        # generated tables are deterministic.
        all_entries = [
            (name, value) for name, value in spec.items() if name != "version"
        ]

        def _is_class_entry(v: object) -> bool:
            if not isinstance(v, dict):
                return False
            if v.get("kind") in (CLASS_KIND, BOXED_UNION_KIND):
                return True
            # `kind = "class"` is also implied by the presence of any
            # class-only sub-table (methods/props/init/constructor_kwonly).
            # Saves a redundant declaration when the rest of the entry
            # already speaks for itself.
            return any(
                k in v for k in ("methods", "props", "init", "constructor_kwonly")
            )

        wrappers = [(n, v) for n, v in all_entries if not _is_class_entry(v)]
        classes = [(n, v) for n, v in all_entries if _is_class_entry(v)]
        wrappers.sort(key=lambda item: item[0])
        classes.sort(key=lambda item: item[0])

        for wrapper_name, wrapper_spec in wrappers:
            wrapper_id = ident(f"{ns_id}_{wrapper_name}")
            params = wrapper_spec.get("params", [])
            call_map = wrapper_spec.get("call", {})

            lines.append(f"static const GoiOverlayParamSpec params_{wrapper_id}[] = {{")
            if not params:
                # ISO C forbids empty initializer braces; emit a zero element.
                lines.append(
                    "    { NULL, GOI_OVERLAY_PARAM_REQUIRED, "
                    "GOI_OVERLAY_DEFAULT_NONE, NULL, 0LL, 0 },"
                )
            for param in params:
                lines.append(emit_param_row(param))
            lines.append("};")
            lines.append("")

            # Tuple literals expand to a static GoiOverlayTupleItem[] per
            # call-spec entry that uses one. Emit them upfront so the spec
            # row can reference the array by name.
            tuple_arrays: dict[str, str] = {}
            for tup_idx, (call_name, call_value) in enumerate(call_map.items()):
                parsed = parse_call(call_name, call_value)
                tuple_items = parsed[7]
                if tuple_items is None:
                    continue
                arr_name = f"tuple_{wrapper_id}_{tup_idx}"
                tuple_arrays[call_name] = arr_name
                lines.append(f"static const GoiOverlayTupleItem {arr_name}[] = {{")
                for item_kind, ival, bval, sval in tuple_items:
                    lines.append(
                        "    { %s, %s, %s, %s },"
                        % (
                            item_kind,
                            c_int(ival),
                            c_bool(bval),
                            c_string_or_null(sval),
                        )
                    )
                lines.append("};")
                lines.append("")

            lines.append(f"static const GoiOverlayCallSpec calls_{wrapper_id}[] = {{")
            if not call_map:
                # Zero-filled placeholder row for empty maps.
                lines.append(
                    "    { NULL, GOI_OVERLAY_CALL_IDENTITY, NULL, NULL, "
                    "0LL, 0, NULL, NULL, 0 },"
                )
            for call_name, call_value in call_map.items():
                name, kind, from_name, value_name, vi, vb, vs, tup = parse_call(
                    call_name, call_value
                )
                if tup is not None:
                    arr_name = tuple_arrays[call_name]
                    tuple_ref = arr_name
                    tuple_len = len(tup)
                else:
                    tuple_ref = None
                    tuple_len = 0
                lines.append(
                    "    { %s, %s, %s, %s, %s, %s, %s, %s, %d },"
                    % (
                        c_string(name),
                        kind,
                        c_string_or_null(from_name),
                        c_string_or_null(value_name),
                        c_int(vi),
                        c_bool(vb),
                        c_string_or_null(vs),
                        tuple_ref if tuple_ref is not None else "NULL",
                        tuple_len,
                    )
                )
            lines.append("};")
            lines.append("")

        lines.append(f"static const GoiCompiledOverrideKV entries_{ns_id}[] = {{")
        for wrapper_name, wrapper_spec in wrappers:
            wrapper_id = ident(f"{ns_id}_{wrapper_name}")
            kind_str = wrapper_spec.get("kind", "function")
            kind_enum = ENTRY_KINDS.get(kind_str)
            if kind_enum is None:
                raise ValueError(
                    f"{path}: overlay entry {wrapper_name!r} has unknown kind {kind_str!r}"
                )
            if kind_str == "internal":
                target_identifier = wrapper_spec.get("internal", wrapper_name)
            elif kind_str == "synthetic":
                # Synthetic entries reuse the typelib's GI info under the
                # exported name — no shadow target needed.
                target_identifier = wrapper_spec.get("shadows", wrapper_name)
            elif kind_str == "alias":
                # Alias entries store the dotted target path
                # ("UserDirectory.DIRECTORY_PICTURES") in `identifier`;
                # the runtime walks it via PyObject_GetAttrString.
                target_identifier = wrapper_spec.get("target")
                if target_identifier is None:
                    raise KeyError(
                        f"{path}: overlay alias {wrapper_name!r} needs 'target'"
                    )
            else:
                target_identifier = wrapper_spec.get("shadows")
                if target_identifier is None:
                    raise KeyError(
                        f"{path}: overlay entry {wrapper_name!r} needs 'shadows'"
                    )
            ret_kind, ret_from, ret_int, ret_bool, ret_string = parse_return(
                wrapper_spec.get("return")
            )
            lines.append(
                "    { %s, { %s, %s, params_%s, %d, calls_%s, %d, "
                "{ %s, %s, %s, %s, %s } } },"
                % (
                    c_string(wrapper_name),
                    kind_enum,
                    c_string(target_identifier),
                    wrapper_id,
                    len(wrapper_spec.get("params", [])),
                    wrapper_id,
                    len(wrapper_spec.get("call", {})),
                    ret_kind,
                    c_string_or_null(ret_from),
                    c_int(ret_int),
                    c_bool(ret_bool),
                    c_string_or_null(ret_string),
                )
            )
        lines.append("};")
        lines.append("")

        # Class entries — one GoiOverlayClassProp[] per class, then a
        # GoiOverlayClassEntry[] referencing them.
        class_arrays_emitted = False
        for class_name, class_spec in classes:
            class_id = ident(f"{ns_id}_class_{class_name}")
            props = class_spec.get("props", {}) or {}
            init_kwargs = class_spec.get("init", []) or []
            constructor_kwonly = class_spec.get("constructor_kwonly", False)
            if not isinstance(init_kwargs, list):
                raise ValueError(
                    f"{path}: class {class_name!r} init must be a list, got {init_kwargs!r}"
                )
            if not isinstance(constructor_kwonly, bool):
                raise ValueError(
                    f"{path}: class {class_name!r} constructor_kwonly must be a bool, "
                    f"got {constructor_kwonly!r}"
                )
            prop_items = sorted(props.items(), key=lambda it: it[0])
            lines.append(f"static const GoiOverlayClassProp props_{class_id}[] = {{")
            if not prop_items:
                lines.append("    { NULL, NULL, NULL },")
            for pname, pspec in prop_items:
                if not isinstance(pspec, dict):
                    raise ValueError(
                        f"{path}: class {class_name!r} prop {pname!r}: "
                        f"expected a table, got {pspec!r}"
                    )
                lines.append(
                    "    { %s, %s, %s },"
                    % (
                        c_string(pname),
                        c_string_or_null(pspec.get("getter")),
                        c_string_or_null(pspec.get("setter")),
                    )
                )
            lines.append("};")
            lines.append("")
            lines.append(f"static const char *init_kwargs_{class_id}[] = {{")
            if not init_kwargs:
                lines.append("    NULL,")
            for kw in init_kwargs:
                lines.append(f"    {c_string(kw)},")
            lines.append("};")
            lines.append("")
            methods = class_spec.get("methods", {}) or {}
            method_items = sorted(methods.items(), key=lambda it: it[0])
            # Emit per-method param/call arrays + a GoiOverlayEntry stub
            # for any method that declares `params = [...]`. The
            # class-method row points at the entry; the lazy lookup
            # installs an overlay-aware descriptor using that entry,
            # giving class methods the same keyword-default /
            # variadic-packing / call-rename treatment top-level
            # overlays get.
            for mname, mspec in method_items:
                if not isinstance(mspec, dict):
                    raise ValueError(
                        f"{path}: class {class_name!r} method {mname!r}: "
                        f"expected a table, got {mspec!r}"
                    )
                m_id = ident(f"{class_id}_method_{mname}")
                mparams = mspec.get("params", []) or []
                if not mparams:
                    continue
                m_call_map = mspec.get("call", {}) or {}
                lines.append(f"static const GoiOverlayParamSpec params_{m_id}[] = {{")
                for param in mparams:
                    lines.append(emit_param_row(param))
                lines.append("};")
                lines.append("")
                # Tuple-literal call values aren't supported for class
                # methods yet — the existing pygobject-compat methods
                # only need identity/rename. Keep the emission simple.
                lines.append(f"static const GoiOverlayCallSpec calls_{m_id}[] = {{")
                if not m_call_map:
                    lines.append(
                        "    { NULL, GOI_OVERLAY_CALL_IDENTITY, NULL, NULL, "
                        "0LL, 0, NULL, NULL, 0 },"
                    )
                else:
                    for c_name, c_value in m_call_map.items():
                        nm, kind, from_name, value_name, vi, vb, vs, tup = parse_call(
                            c_name, c_value
                        )
                        if tup is not None:
                            raise ValueError(
                                f"{path}: class {class_name!r} method {mname!r} "
                                f"call {c_name!r}: tuple literals unsupported"
                            )
                        lines.append(
                            "    { %s, %s, %s, %s, %s, %s, %s, NULL, 0 },"
                            % (
                                c_string(nm),
                                kind,
                                c_string_or_null(from_name),
                                c_string_or_null(value_name),
                                c_int(vi),
                                c_bool(vb),
                                c_string_or_null(vs),
                            )
                        )
                lines.append("};")
                lines.append("")
                lines.append(f"static const GoiOverlayEntry entry_{m_id} = {{")
                lines.append("    GOI_OVERLAY_KIND_FUNCTION,")
                lines.append("    NULL,")  # identifier — class method, not top-level
                lines.append(f"    params_{m_id},")
                lines.append(f"    {len(mparams)},")
                lines.append(f"    calls_{m_id},")
                lines.append(f"    {len(m_call_map)},")
                lines.append(
                    "    { GOI_OVERLAY_RETURN_PASSTHROUGH, NULL, 0LL, 0, NULL },"
                )
                lines.append("};")
                lines.append("")
            lines.append(
                f"static const GoiOverlayClassMethod methods_{class_id}[] = {{"
            )
            if not method_items:
                lines.append("    { NULL, 0, NULL, NULL },")
            for mname, mspec in method_items:
                trailing_user_data = mspec.get("trailing_user_data", False)
                if not isinstance(trailing_user_data, bool):
                    raise ValueError(
                        f"{path}: class {class_name!r} method {mname!r}: "
                        f"trailing_user_data must be a bool, got {trailing_user_data!r}"
                    )
                from_function = mspec.get("from_function")
                if from_function is not None and not isinstance(from_function, str):
                    raise ValueError(
                        f"{path}: class {class_name!r} method {mname!r}: "
                        f"from_function must be a str, got {from_function!r}"
                    )
                m_id = ident(f"{class_id}_method_{mname}")
                mparams = mspec.get("params", []) or []
                entry_ref = f"&entry_{m_id}" if mparams else "NULL"
                lines.append(
                    "    { %s, %s, %s, %s },"
                    % (
                        c_string(mname),
                        c_bool(trailing_user_data),
                        c_string(from_function)
                        if from_function is not None
                        else "NULL",
                        entry_ref,
                    )
                )
            lines.append("};")
            lines.append("")
            class_arrays_emitted = True

            # `kind = "boxed_union"` arms table. Only emitted for
            # classes that declare it; other classes get NULL/0 fields
            # in the row.
            if class_spec.get("kind") == BOXED_UNION_KIND:
                discriminator = class_spec.get("discriminator")
                discriminator_enum = class_spec.get("discriminator_enum")
                arms = class_spec.get("arms", {}) or {}
                if not isinstance(discriminator, str):
                    raise ValueError(
                        f"{path}: class {class_name!r}: boxed_union "
                        f"requires `discriminator` (str)"
                    )
                if not isinstance(discriminator_enum, str):
                    raise ValueError(
                        f"{path}: class {class_name!r}: boxed_union "
                        f"requires `discriminator_enum` (str)"
                    )
                if not isinstance(arms, dict) or not arms:
                    raise ValueError(
                        f"{path}: class {class_name!r}: boxed_union "
                        f"requires a non-empty `arms` table"
                    )
                lines.append(
                    f"static const GoiOverlayBoxedUnionArm "
                    f"boxed_union_arms_{class_id}[] = {{"
                )
                for enum_name, arm_member in arms.items():
                    if not isinstance(arm_member, str):
                        raise ValueError(
                            f"{path}: class {class_name!r}: arm "
                            f"{enum_name!r} member must be a string"
                        )
                    lines.append(
                        "    { %s, %s }," % (c_string(enum_name), c_string(arm_member))
                    )
                lines.append("};")
                lines.append("")

        if classes:
            lines.append(
                f"static const GoiOverlayClassEntry class_entries_{ns_id}[] = {{"
            )
            for class_name, class_spec in classes:
                class_id = ident(f"{ns_id}_class_{class_name}")
                props = class_spec.get("props", {}) or {}
                init_kwargs = class_spec.get("init", []) or []
                methods = class_spec.get("methods", {}) or {}
                constructor_kwonly = class_spec.get("constructor_kwonly", False)
                if class_spec.get("kind") == BOXED_UNION_KIND:
                    bu_disc = c_string(class_spec["discriminator"])
                    bu_enum = c_string(class_spec["discriminator_enum"])
                    bu_arms_ref = f"boxed_union_arms_{class_id}"
                    bu_n_arms = len(class_spec.get("arms", {}) or {})
                else:
                    bu_disc = "NULL"
                    bu_enum = "NULL"
                    bu_arms_ref = "NULL"
                    bu_n_arms = 0
                lines.append(
                    "    { %s, props_%s, %d, init_kwargs_%s, %d, %s, "
                    "methods_%s, %d, %s, %s, %s, %d },"
                    % (
                        c_string(class_name),
                        class_id,
                        len(props),
                        class_id,
                        len(init_kwargs),
                        c_bool(constructor_kwonly),
                        class_id,
                        len(methods),
                        bu_disc,
                        bu_enum,
                        bu_arms_ref,
                        bu_n_arms,
                    )
                )
            lines.append("};")
            lines.append("")
        del class_arrays_emitted

        # Emit the `[__namespace__]` arrays, if any. Empty stanzas mean
        # the namespace has no first-access directives — the row gets
        # `NULL, 0` fields and the runtime skips them.
        require_list: list[str] = []
        first_access_calls: list[tuple[str, str | None, bool]] = []
        if ns_meta is not None:
            if not isinstance(ns_meta, dict):
                raise ValueError(
                    f"{path}: [__namespace__] must be a table, got {ns_meta!r}"
                )
            req = ns_meta.get("require", [])
            if not isinstance(req, list) or not all(isinstance(r, str) for r in req):
                raise ValueError(
                    f"{path}: [__namespace__].require must be a list of strings"
                )
            require_list = cast("list[str]", list(req))
            calls = ns_meta.get("call_on_first_access", [])
            if not isinstance(calls, list):
                raise ValueError(
                    f"{path}: [__namespace__].call_on_first_access must be a list"
                )
            for c in calls:
                if not isinstance(c, dict) or "function" not in c:
                    raise ValueError(
                        f"{path}: call_on_first_access entry must be a table "
                        f"with a `function` key, got {c!r}"
                    )
                fn = c["function"]
                if not isinstance(fn, str):
                    raise ValueError(
                        f"{path}: call_on_first_access function must be a string"
                    )
                env_gate = c.get("env_gate")
                if env_gate is not None and not isinstance(env_gate, str):
                    raise ValueError(
                        f"{path}: call_on_first_access env_gate must be a "
                        f"string or absent"
                    )
                on_error = c.get("on_error", "raise")
                if on_error not in ("raise", "warn"):
                    raise ValueError(
                        f"{path}: call_on_first_access on_error must be "
                        f"'raise' or 'warn', got {on_error!r}"
                    )
                first_access_calls.append((fn, env_gate, on_error == "warn"))

        if require_list:
            lines.append(f"static const char *const require_{ns_id}[] = {{")
            for r in require_list:
                lines.append(f"    {c_string(r)},")
            lines.append("};")
            lines.append("")
            require_ref = f"require_{ns_id}"
        else:
            require_ref = "NULL"

        if first_access_calls:
            lines.append(
                f"static const GoiNamespaceFirstAccessCall first_access_{ns_id}[] = {{"
            )
            for fn, env_gate, warn in first_access_calls:
                lines.append(
                    "    { %s, %s, %s },"
                    % (c_string(fn), c_string_or_null(env_gate), c_bool(warn))
                )
            lines.append("};")
            lines.append("")
            first_access_ref = f"first_access_{ns_id}"
        else:
            first_access_ref = "NULL"

        class_entries_ref = f"class_entries_{ns_id}" if classes else "NULL"
        namespace_rows.append(
            "    { %s, %s, entries_%s, %d, %s, %d, %s, %d, %s, %d },"
            % (
                c_string(namespace),
                c_string(version),
                ns_id,
                len(wrappers),
                class_entries_ref,
                len(classes),
                require_ref,
                len(require_list),
                first_access_ref,
                len(first_access_calls),
            )
        )

    lines.append("static const GoiCompiledOverlayNamespace g_namespaces[] = {")
    lines.extend(namespace_rows)
    lines.append("};")
    lines.append("")
    lines.append("const GoiCompiledOverlayNamespace *goi_overlay_lookup_namespace(")
    lines.append("    const char *namespace_name, const char *namespace_version)")
    lines.append("{")
    lines.append('    /* `namespace_version == NULL` means "match any version" — used')
    lines.append(
        "     * by class-build callers that don't carry the version through. */"
    )
    lines.append(
        "    for (size_t i = 0; i < sizeof(g_namespaces) / sizeof(g_namespaces[0]); i++) {"
    )
    lines.append("        const GoiCompiledOverlayNamespace *ns = &g_namespaces[i];")
    lines.append("        if (strcmp(ns->namespace_name, namespace_name) != 0)")
    lines.append("            continue;")
    lines.append("        if (namespace_version == NULL)")
    lines.append("            return ns;")
    lines.append("        if (ns->namespace_version != NULL &&")
    lines.append("            strcmp(ns->namespace_version, namespace_version) == 0)")
    lines.append("            return ns;")
    lines.append("    }")
    lines.append("    return NULL;")
    lines.append("}")
    lines.append("")
    lines.append("const GoiOverlayEntry *goi_overlay_lookup_entry(")
    lines.append(
        "    const GoiCompiledOverlayNamespace *compiled_namespace, const char *exported_name)"
    )
    lines.append("{")
    lines.append("    if (compiled_namespace == NULL || exported_name == NULL)")
    lines.append("        return NULL;")
    lines.append("    for (size_t i = 0; i < compiled_namespace->n_entries; i++) {")
    lines.append(
        "        const GoiCompiledOverrideKV *kv = &compiled_namespace->entries[i];"
    )
    lines.append("        if (strcmp(kv->stem, exported_name) == 0)")
    lines.append("            return &kv->entry;")
    lines.append("    }")
    lines.append("    return NULL;")
    lines.append("}")
    lines.append("")
    lines.append("const GoiOverlayClassEntry *goi_overlay_lookup_class(")
    lines.append(
        "    const GoiCompiledOverlayNamespace *compiled_namespace, const char *class_name)"
    )
    lines.append("{")
    lines.append("    if (compiled_namespace == NULL || class_name == NULL)")
    lines.append("        return NULL;")
    lines.append(
        "    for (size_t i = 0; i < compiled_namespace->n_class_entries; i++) {"
    )
    lines.append(
        "        const GoiOverlayClassEntry *ce = &compiled_namespace->class_entries[i];"
    )
    lines.append("        if (strcmp(ce->class_name, class_name) == 0)")
    lines.append("            return ce;")
    lines.append("    }")
    lines.append("    return NULL;")
    lines.append("}")
    lines.append("")
    lines.append("const GoiOverlayClassMethod *goi_overlay_lookup_class_method(")
    lines.append(
        "    const GoiOverlayClassEntry *class_entry, const char *method_name)"
    )
    lines.append("{")
    lines.append("    if (class_entry == NULL || method_name == NULL)")
    lines.append("        return NULL;")
    lines.append("    for (size_t i = 0; i < class_entry->n_methods; i++) {")
    lines.append("        const GoiOverlayClassMethod *m = &class_entry->methods[i];")
    lines.append("        if (m->name != NULL && strcmp(m->name, method_name) == 0)")
    lines.append("            return m;")
    lines.append("    }")
    lines.append("    return NULL;")
    lines.append("}")

    output.write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
