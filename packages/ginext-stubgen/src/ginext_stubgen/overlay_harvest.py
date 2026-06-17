# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

"""Static harvest of runtime ``@overlay.*`` declarations into stub-overlay dicts.

ginext registers a large Pythonic surface at runtime via ``@overlay.method`` /
``.property`` / ``.add`` / ``.replace`` and the ``.bases`` / ``.constant`` /
``.deprecated`` / ``.alias`` calls in ``src/ginext/_overlays/*.py`` and each
``packages/*/src/*/_overlays/*.py``. This module reads those files **statically**
(``ast`` — no import of ginext or any typelib) and produces, per namespace, an
overlay dict in the same shape ``native_overlays.toml`` uses, so the emitter
merges them into the generated stubs.

A method overlay's public signature is read straight from its ``def``, dropping
a leading ``fn`` parameter exactly as the runtime does
(``registrar._body_overlay_maybe_with_fn``: ``inject_fn = params[0].name ==
"fn"``).
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

# Namespaces whose surface is owned by ginext's inline stubs, not the generated
# package — skip so we don't double-emit / fight the inline source of truth.
_SKIP_NAMESPACES = {"GIRepository"}


@dataclass
class NSOverlay:
    helper_classes: dict[str, str] = field(default_factory=dict)
    module_lines: list[str] = field(default_factory=list)
    # Names of module-level functions/constants replaced by the overlay; the
    # GIR-generated stub for these should be suppressed (last-wins otherwise).
    module_reserves: list[str] = field(default_factory=list)
    class_bodies: dict[str, list[str]] = field(default_factory=dict)
    class_reserves: dict[str, list[str]] = field(default_factory=dict)
    class_extra_bases: dict[str, list[str]] = field(default_factory=dict)


def harvest_overlays(roots: list[Path]) -> dict[str, dict[str, Any]]:
    """Return ``{namespace: overlay_dict}`` harvested from the overlay files."""
    per_ns: dict[str, NSOverlay] = {}
    for path in _discover(roots):
        ns = path.stem
        if ns in _SKIP_NAMESPACES:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except OSError, SyntaxError:
            continue
        acc = per_ns.setdefault(ns, NSOverlay())
        _harvest_module(tree, acc)
    return {ns: dct for ns, acc in per_ns.items() if (dct := _to_overlay_dict(acc))}


def _discover(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        files.extend(sorted((root / "src" / "ginext" / "_overlays").glob("*.py")))
        files.extend(sorted(root.glob("packages/*/src/*/_overlays/*.py")))
    return [f for f in files if f.name != "__init__.py"]


# --------------------------------------------------------------------------
# Module walk
# --------------------------------------------------------------------------


def _harvest_module(tree: ast.Module, acc: NSOverlay) -> None:
    helper_defs: dict[str, ast.ClassDef] = {
        node.name: node for node in tree.body if isinstance(node, ast.ClassDef)
    }
    module_functions: dict[str, ast.FunctionDef] = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    rendered_text: list[str] = []

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            _harvest_decorated_fn(node, acc, rendered_text)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            _harvest_call(node.value, acc, rendered_text, module_functions)

    # Pull in any helper classes referenced by the rendered signatures (and,
    # transitively, helpers those reference).
    text = "\n".join(rendered_text)
    wanted: set[str] = set()
    frontier = [n for n in helper_defs if _word_in(n, text)]
    while frontier:
        name = frontier.pop()
        if name in wanted:
            continue
        wanted.add(name)
        stub = _render_class_stub(helper_defs[name])
        acc.helper_classes[name] = stub
        frontier.extend(n for n in helper_defs if n not in wanted and _word_in(n, stub))


def _harvest_decorated_fn(
    fn: ast.FunctionDef, acc: NSOverlay, rendered: list[str]
) -> None:
    for deco in fn.decorator_list:
        kind = _overlay_decorator(deco)
        if kind is None:
            continue
        verb, args, kwargs = kind
        if verb == "method":
            class_name = _str_arg(args, 0)
            if class_name is None:
                continue
            name = _str_kw(kwargs, "name") or fn.name
            as_static = _bool_kw(kwargs, "as_staticmethod") or _bool_kw(
                kwargs, "staticmethod"
            )
            as_class = _bool_kw(kwargs, "as_classmethod") or _bool_kw(
                kwargs, "classmethod"
            )
            sig = _render_func(fn, name=name, static=as_static, classmethod_=as_class)
            acc.class_bodies.setdefault(class_name, []).append(sig)
            acc.class_reserves.setdefault(class_name, []).append(name)
            rendered.append(sig)
        elif verb == "property":
            class_name = _str_arg(args, 0)
            if class_name is None:
                continue
            sig = _render_func(fn, name=fn.name, decorator="@property")
            acc.class_bodies.setdefault(class_name, []).append(sig)
            acc.class_reserves.setdefault(class_name, []).append(fn.name)
            rendered.append(sig)
        elif verb in ("add", "replace"):
            # Module-level function. `add("Target")` may rename; else use fn name.
            target = _str_arg(args, 0)
            name = (
                target.split(".")[-1] if target and "." in target else target
            ) or fn.name
            sig = _render_func(fn, name=name)
            acc.module_lines.append(sig)
            acc.module_reserves.append(name)
            rendered.append(sig)
        return


def _harvest_call(
    call: ast.Call,
    acc: NSOverlay,
    rendered: list[str],
    module_functions: dict[str, ast.FunctionDef],
) -> None:
    verb = _overlay_method_name(call.func)
    if verb is None:
        return
    if verb == "bases":
        class_name = _str_arg(call.args, 0)
        if class_name is None or len(call.args) < 2:
            return
        bases = _str_list(call.args[1])
        if bases:
            acc.class_extra_bases.setdefault(class_name, []).extend(bases)
    elif verb in ("constant", "deprecated", "alias"):
        line = _render_module_value(verb, call, module_functions)
        if line:
            acc.module_lines.append(line)
            name = _str_arg(call.args, 0)
            if name is not None:
                acc.module_reserves.append(name)
            rendered.append(line)
    elif verb == "constants":
        # constants({"NAME": value, ...}) — emit each as Any (values are runtime
        # objects; their precise type isn't statically recoverable here).
        if call.args and isinstance(call.args[0], ast.Dict):
            for key in call.args[0].keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    acc.module_lines.append(f"{key.value}: Any")


def _render_module_value(
    verb: str,
    call: ast.Call,
    module_functions: dict[str, ast.FunctionDef],
) -> str | None:
    name = _str_arg(call.args, 0)
    if name is None:
        return None
    if verb == "alias":
        # alias(source, target): target = source
        target = _str_arg(call.args, 1)
        if target is None:
            return None
        return f"{target} = {name}"
    # constant(name, value) / deprecated(name, value, replacement): alias to the
    # value expression when it's a resolvable public name/attribute; else
    # annotate Any.  Private names (starting with _) are runtime-only helpers
    # that don't exist in the stub namespace.
    if len(call.args) >= 2:
        value = call.args[1]
        if isinstance(value, ast.Name) and value.id in module_functions:
            return _render_func(module_functions[value.id], name=name)
        if isinstance(value, (ast.Name, ast.Attribute)):
            expr = ast.unparse(value)
            base = expr.split(".")[0]
            if not base.startswith("_"):
                return f"{name} = {expr}"
    return f"{name}: Any"


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def _render_func(
    fn: ast.FunctionDef,
    *,
    name: str,
    static: bool = False,
    classmethod_: bool = False,
    decorator: str | None = None,
) -> str:
    params = list(fn.args.args)
    # Drop the injected original-callable param (runtime: params[0].name == "fn").
    injected_fn = params and params[0].arg == "fn"
    if injected_fn:
        params = params[1:]
    # defaults is right-aligned against params. After stripping "fn", offset
    # the alignment by 1 if we removed it (only when "fn" had a default, which
    # never happens in practice — but keep the math correct).
    raw_defaults = list(fn.args.defaults)
    if injected_fn and len(raw_defaults) == len(fn.args.args):
        # The defaults list included a slot for the removed "fn" param.
        raw_defaults = raw_defaults[1:]
    # Pad left so defaults[i] aligns with params[i].
    n_no_default = len(params) - len(raw_defaults)
    padded_defaults: list[ast.expr | None] = [None] * n_no_default + list(raw_defaults)
    pieces: list[str] = []
    for arg, default in zip(params, padded_defaults):
        pieces.append(_render_arg(arg, default))
    if fn.args.vararg is not None:
        pieces.append("*" + _render_arg(fn.args.vararg))
    for arg, kw_default in zip(fn.args.kwonlyargs, fn.args.kw_defaults):
        pieces.append(_render_arg(arg, kw_default))
    if fn.args.kwarg is not None:
        pieces.append("**" + _render_arg(fn.args.kwarg))
    ret = f" -> {ast.unparse(fn.returns)}" if fn.returns is not None else ""
    head = f"def {name}({', '.join(pieces)}){ret}: ..."
    decos = []
    if decorator:
        decos.append(decorator)
    if static:
        decos.append("@staticmethod")
    if classmethod_:
        decos.append("@classmethod")
    return "\n".join([*decos, head])


def _render_arg(arg: ast.arg, default: ast.expr | None = None) -> str:
    base = (
        f"{arg.arg}: {ast.unparse(arg.annotation)}"
        if arg.annotation is not None
        else arg.arg
    )
    if default is not None:
        return f"{base} = ..."
    return base


def _render_class_stub(cls: ast.ClassDef) -> str:
    bases = ", ".join(ast.unparse(b) for b in cls.bases)
    header = f"class {cls.name}" + (f"({bases})" if bases else "") + ":"
    body: list[str] = []
    for stmt in cls.body:
        if isinstance(stmt, ast.FunctionDef):
            decos = [f"@{ast.unparse(d)}" for d in stmt.decorator_list]
            sig = _render_func(stmt, name=stmt.name)
            for line in [*decos, *sig.splitlines()]:
                body.append("    " + line)
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            body.append(f"    {stmt.target.id}: {ast.unparse(stmt.annotation)}")
    if not body:
        body.append("    ...")
    return "\n".join([header, *body])


# --------------------------------------------------------------------------
# Decorator / call recognition
# --------------------------------------------------------------------------


def _overlay_decorator(
    deco: ast.expr,
) -> tuple[str, list[ast.expr], list[ast.keyword]] | None:
    """Return (verb, args, kwargs) for an ``@overlay.<verb>`` decorator."""
    if isinstance(deco, ast.Call):
        verb = _overlay_method_name(deco.func)
        if verb is not None:
            return verb, list(deco.args), list(deco.keywords)
        return None
    verb = _overlay_method_name(deco)  # bare ``@overlay.add`` / ``@overlay.replace``
    if verb is not None:
        return verb, [], []
    return None


def _overlay_method_name(func: ast.expr) -> str | None:
    if (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "overlay"
    ):
        return func.attr
    return None


# --------------------------------------------------------------------------
# Small AST helpers
# --------------------------------------------------------------------------


def _str_arg(args: list[ast.expr], i: int) -> str | None:
    if i < len(args) and isinstance(args[i], ast.Constant):
        node = args[i]
        assert isinstance(node, ast.Constant)
        v = node.value
        return v if isinstance(v, str) else None
    return None


def _str_kw(kwargs: list[ast.keyword], name: str) -> str | None:
    for kw in kwargs:
        if kw.arg == name and isinstance(kw.value, ast.Constant):
            v = kw.value.value
            return v if isinstance(v, str) else None
    return None


def _bool_kw(kwargs: list[ast.keyword], name: str) -> bool:
    for kw in kwargs:
        if kw.arg == name and isinstance(kw.value, ast.Constant):
            return bool(kw.value.value)
    return False


def _str_list(node: ast.expr) -> list[str]:
    if not isinstance(node, (ast.List, ast.Tuple)):
        return []
    out: list[str] = []
    for el in node.elts:
        if isinstance(el, ast.Constant) and isinstance(el.value, str):
            out.append(el.value)
        elif isinstance(el, (ast.Name, ast.Attribute)):
            out.append(ast.unparse(el))
    return out


def _word_in(name: str, text: str) -> bool:
    return re.search(rf"\b{re.escape(name)}\b", text) is not None


# --------------------------------------------------------------------------
# Assemble the native_overlays.toml-shaped dict
# --------------------------------------------------------------------------


def _to_overlay_dict(acc: NSOverlay) -> dict[str, Any]:
    out: dict[str, Any] = {}
    prelude_parts: list[str] = []
    prelude_parts.extend(acc.helper_classes.values())
    prelude_parts.extend(acc.module_lines)
    if prelude_parts:
        out["prelude"] = "\n\n".join(prelude_parts)
    if acc.module_reserves:
        out["module_reserves"] = list(dict.fromkeys(acc.module_reserves))
    classes: dict[str, Any] = {}
    names = set(acc.class_bodies) | set(acc.class_extra_bases)
    for name in names:
        entry: dict[str, Any] = {}
        if name in acc.class_bodies:
            entry["body"] = "\n".join(acc.class_bodies[name])
            entry["reserves"] = acc.class_reserves.get(name, [])
        if name in acc.class_extra_bases:
            entry["extra_bases"] = acc.class_extra_bases[name]
        classes[name] = entry
    if classes:
        out["classes"] = classes
    return out
