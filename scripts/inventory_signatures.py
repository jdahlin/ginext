#!/usr/bin/env python3

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

"""Cross-reference the per-namespace JSON output from `inventory_sweep.py`
with the GIR XML on disk to figure out which concrete *types* are
driving each rejection bucket.

Reads `/tmp/ginext-inventory/*.json` (overrideable) and the GIR XML in
`/usr/share/gir-1.0/`, then prints histograms of types that appear in
the rejected callables' signatures. Use `--bucket` to focus on one
rejection reason, `--namespace` to focus on one namespace.

    PYTHONPATH=build/cpython-3.14t/src \\
        .venv-cpython-3.14t/bin/python3 scripts/inventory_signatures.py \\
        --bucket "unsupported argument type"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

GI_NS = "http://www.gtk.org/introspection/core/1.0"
C_NS = "http://www.gtk.org/introspection/c/1.0"
GLIB_NS = "http://www.gtk.org/introspection/glib/1.0"

_QUALIFIED_PREFIX = re.compile(r"^[A-Za-z_][\w.]*:\s*")


def normalize_reason(message: str) -> str:
    return _QUALIFIED_PREFIX.sub("", message).strip()


def tag(local: str) -> str:
    return f"{{{GI_NS}}}{local}"


CONTAINER_KINDS = {tag("class"), tag("interface"), tag("record"), tag("union")}
CALLABLE_KINDS = {
    tag("method"),
    tag("function"),
    tag("constructor"),
    tag("virtual-method"),
}


def render_type(node: ET.Element) -> str:
    """Compact, human-readable rendering of a <return-value> or
    <parameter>'s child type element."""
    # The child element is either <type>, <array>, or <varargs>.
    type_node = None
    for child in node:
        if child.tag in (tag("type"), tag("array"), tag("varargs")):
            type_node = child
            break
    if type_node is None:
        return "void"
    return _render(type_node)


def _render(node: ET.Element) -> str:
    if node.tag == tag("varargs"):
        return "varargs"
    if node.tag == tag("array"):
        zero_terminated = node.attrib.get("zero-terminated", "0") == "1"
        fixed = node.attrib.get("fixed-size")
        length = node.attrib.get("length")
        c_type = node.attrib.get(f"{{{C_NS}}}type", "")
        inner = "?"
        for child in node:
            if child.tag in (tag("type"), tag("array")):
                inner = _render(child)
                break
        if fixed:
            return f"array[{fixed}]<{inner}>"
        if length is not None:
            return f"array(len_arg)<{inner}>"
        if zero_terminated:
            return f"zarray<{inner}>"
        if "**" in c_type:
            return f"array<{inner}>"
        return f"array<{inner}>"
    name = node.attrib.get("name", "?")
    children = [_render(c) for c in node if c.tag in (tag("type"), tag("array"))]
    if children:
        return f"{name}<{', '.join(children)}>"
    return name


def index_namespace(gir_path: Path) -> dict[str, ET.Element]:
    """Return a dict of qualified-name → callable Element for one .gir.
    Names follow our sweep's qualified format, e.g. ``Gtk.Application.get_windows``
    for methods or ``Gtk.foo`` for top-level functions."""
    tree = ET.parse(gir_path)
    root = tree.getroot()
    namespace_el = root.find(tag("namespace"))
    if namespace_el is None:
        return {}
    ns_name = namespace_el.attrib.get("name", "")
    index: dict[str, ET.Element] = {}

    for child in namespace_el:
        if child.tag == tag("function"):
            name = child.attrib.get("name") or ""
            index[f"{ns_name}.{name.replace('-', '_')}"] = child
        elif child.tag in CONTAINER_KINDS:
            container_name = child.attrib.get("name") or ""
            for inner in child:
                if inner.tag in CALLABLE_KINDS:
                    method_name = inner.attrib.get("name") or ""
                    qualified = (
                        f"{ns_name}.{container_name}.{method_name.replace('-', '_')}"
                    )
                    index[qualified] = inner
    return index


class GirCache:
    def __init__(self, gir_dirs: list[Path]) -> None:
        self.gir_dirs = [d for d in gir_dirs if d.is_dir()]
        self._indices: dict[str, dict[str, ET.Element]] = {}
        self._missing: set[str] = set()

    def _path_for(self, namespace: str, version: str) -> Path | None:
        for gir_dir in self.gir_dirs:
            candidate = gir_dir / f"{namespace}-{version}.gir"
            if candidate.exists():
                return candidate
        for gir_dir in self.gir_dirs:
            glob = sorted(gir_dir.glob(f"{namespace}-*.gir"))
            if glob:
                return glob[0]
        return None

    def get(self, namespace: str, version: str) -> dict[str, ET.Element]:
        if namespace in self._indices:
            return self._indices[namespace]
        if namespace in self._missing:
            return {}
        path = self._path_for(namespace, version)
        if path is None:
            self._missing.add(namespace)
            return {}
        try:
            self._indices[namespace] = index_namespace(path)
        except ET.ParseError as exc:
            print(f"warning: failed to parse {path}: {exc}", file=sys.stderr)
            self._missing.add(namespace)
            return {}
        return self._indices[namespace]


def callable_signature(element: ET.Element) -> dict[str, Any]:
    return_el = element.find(tag("return-value"))
    return_type = render_type(return_el) if return_el is not None else "void"
    return_transfer = (
        return_el.attrib.get("transfer-ownership", "") if return_el is not None else ""
    )

    parameters: list[dict[str, Any]] = []
    params_root = element.find(tag("parameters"))
    if params_root is not None:
        for param in params_root:
            if param.tag not in (tag("parameter"), tag("instance-parameter")):
                continue
            entry = {
                "name": param.attrib.get("name", ""),
                "instance": param.tag == tag("instance-parameter"),
                "direction": param.attrib.get("direction", "in"),
                "transfer": param.attrib.get("transfer-ownership", ""),
                "type": render_type(param),
                "caller_allocates": param.attrib.get("caller-allocates", "0") == "1",
                "nullable": param.attrib.get("nullable", "0") == "1",
                "optional": param.attrib.get("optional", "0") == "1",
            }
            parameters.append(entry)

    can_throw = element.attrib.get("throws", "0") == "1"
    return {
        "return": return_type,
        "return_transfer": return_transfer,
        "params": parameters,
        "throws": can_throw,
    }


def types_in_signature(sig: dict[str, Any], *, role: str) -> list[str]:
    """Pull the type strings most relevant for one rejection role."""
    if role == "return":
        return [sig["return"]]
    if role == "args-in":
        return [
            p["type"]
            for p in sig["params"]
            if not p["instance"] and p["direction"] == "in"
        ]
    if role == "args-out":
        return [
            f"{p['direction']} {p['type']}"
            for p in sig["params"]
            if not p["instance"] and p["direction"] != "in"
        ]
    if role == "all":
        out: list[str] = [sig["return"]]
        for p in sig["params"]:
            if p["instance"]:
                continue
            tag_str = p["type"]
            if p["direction"] != "in":
                tag_str = f"{p['direction']} {tag_str}"
            out.append(tag_str)
        return out
    raise ValueError(role)


def role_for_reason(reason: str) -> str:
    if "unsupported return type" in reason:
        return "return"
    if "unsupported argument type" in reason:
        return "args-in"
    if "out and inout arguments" in reason:
        return "args-out"
    return "all"


def format_signature(sig: dict[str, Any]) -> str:
    args: list[str] = []
    for p in sig["params"]:
        if p["instance"]:
            continue
        prefix = ""
        if p["direction"] != "in":
            prefix = f"{p['direction']} "
        suffix = ""
        if p["caller_allocates"]:
            suffix = " [caller-alloc]"
        args.append(f"{prefix}{p['name']}: {p['type']}{suffix}")
    args_str = ", ".join(args)
    suffix = " throws" if sig["throws"] else ""
    return f"({args_str}) -> {sig['return']}{suffix}"


def collect_supported_types(
    cache: GirCache,
    json_paths: list[Path],
    only_ns: set[str] | None,
) -> set[str]:
    """Return the set of type strings observed anywhere in a successfully
    built callable. Used to filter "background" types out of the rejected
    histogram so only the genuine offenders surface."""
    supported: set[str] = set()
    rejected_keys: dict[str, set[str]] = defaultdict(set)
    for path in json_paths:
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        ns = data.get("namespace")
        ver = data.get("version", "")
        if only_ns and ns not in only_ns:
            continue
        for rejection in data.get("rejections", ()):
            rejected_keys[ns].add(rejection["qualified"])
        if data.get("built", 0) == 0:
            continue
        index = cache.get(ns, ver)
        if not index:
            continue
        rejected_for_ns = rejected_keys[ns]
        for qualified, element in index.items():
            if qualified in rejected_for_ns:
                continue
            sig = callable_signature(element)
            supported.add(sig["return"])
            for p in sig["params"]:
                if p["instance"]:
                    continue
                token = p["type"]
                if p["direction"] != "in":
                    token = f"{p['direction']} {token}"
                supported.add(token)
    return supported


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inventory-dir",
        default="/tmp/ginext-inventory",
        type=Path,
        help="Directory containing per-namespace JSONs from inventory_sweep.py.",
    )
    parser.add_argument(
        "--gir-dir",
        action="append",
        default=None,
        type=Path,
        help=(
            "Directory containing .gir XML files. May be repeated. "
            "Default: /usr/share/gir-1.0 and /usr/lib/x86_64-linux-gnu/gir-1.0."
        ),
    )
    parser.add_argument(
        "--bucket",
        default="unsupported argument type",
        help=(
            "Only show signatures from this rejection bucket "
            "(substring match against the normalized reason). "
            "Default: 'unsupported argument type'."
        ),
    )
    parser.add_argument(
        "--namespace",
        action="append",
        default=None,
        help="Limit to these namespaces. May be repeated.",
    )
    parser.add_argument(
        "--top-types",
        type=int,
        default=30,
        help="Show this many type buckets (default: 30).",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=6,
        help="Sample callables to list per type (default: 6).",
    )
    parser.add_argument(
        "--dump-signatures",
        action="store_true",
        help="After the histogram, dump full signatures grouped by type.",
    )
    parser.add_argument(
        "--no-baseline-filter",
        action="store_true",
        help=(
            "Skip the supported-types baseline filter. Default filters out "
            "any type that also appears in a successfully built signature, "
            "so only types that are *only* seen in rejections survive."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    gir_dirs = args.gir_dir or [
        Path("/usr/share/gir-1.0"),
        Path("/usr/lib/x86_64-linux-gnu/gir-1.0"),
    ]
    cache = GirCache(gir_dirs)

    json_paths = sorted(args.inventory_dir.glob("*.json"))
    if not json_paths:
        print(f"no JSON files in {args.inventory_dir}", file=sys.stderr)
        return 1

    only_ns = set(args.namespace) if args.namespace else None
    type_counter: Counter[str] = Counter()
    type_samples: dict[str, list[tuple[str, str]]] = defaultdict(list)
    matched = 0
    skipped_lookup = 0
    examined_reasons: Counter[str] = Counter()

    for path in json_paths:
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        ns = data.get("namespace")
        ver = data.get("version", "")
        if only_ns and ns not in only_ns:
            continue
        rejections = data.get("rejections", [])
        if not rejections:
            continue
        index = cache.get(ns, ver)
        for rejection in rejections:
            reason = normalize_reason(rejection["reason"])
            examined_reasons[reason] += 1
            if args.bucket not in reason:
                continue
            qualified = rejection["qualified"]
            element = index.get(qualified)
            if element is None:
                skipped_lookup += 1
                continue
            sig = callable_signature(element)
            role = role_for_reason(reason)
            for type_str in types_in_signature(sig, role=role):
                type_counter[type_str] += 1
                type_samples[type_str].append((qualified, format_signature(sig)))
            matched += 1

    print(f"matched {matched} rejected callables (bucket={args.bucket!r})")
    if skipped_lookup:
        print(f"  ({skipped_lookup} skipped because XML element not found)")
    if only_ns:
        print(f"  namespaces filter: {sorted(only_ns)}")

    if not args.no_baseline_filter:
        supported = collect_supported_types(cache, json_paths, only_ns)
        before = len(type_counter)
        for type_str in list(type_counter):
            if type_str in supported:
                del type_counter[type_str]
        print(
            f"  baseline filter: kept {len(type_counter)} of {before} types "
            f"(removed any seen in a successfully built signature)"
        )

    print()
    print("=" * 72)
    print(f"Top {args.top_types} types in rejected callables")
    print("=" * 72)
    for type_str, count in type_counter.most_common(args.top_types or None):
        print(f"  {count:>5}  {type_str}")
        for qualified, sig_str in type_samples[type_str][: args.samples]:
            print(f"           - {qualified}  {sig_str}")
        if count > args.samples:
            print(f"           ... and {count - args.samples} more")

    if args.dump_signatures:
        print()
        print("=" * 72)
        print("Full signatures grouped by type")
        print("=" * 72)
        for type_str, count in type_counter.most_common(args.top_types or None):
            print()
            print(f"# {type_str}  ({count})")
            for qualified, sig_str in type_samples[type_str]:
                print(f"  {qualified}  {sig_str}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
