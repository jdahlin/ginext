from __future__ import annotations

from collections.abc import Callable

from mypy.nodes import AssignmentStmt, NameExpr, StrExpr, TypeInfo
from mypy.plugin import ClassDefContext, Plugin

_GOBJECT_OBJECT = "ginext.GObject.Object"


def _is_native_gobject_type(info: TypeInfo) -> bool:
    return any(base.fullname == _GOBJECT_OBJECT for base in info.mro)


def _is_native_gobject_base(plugin: Plugin, fullname: str) -> bool:
    if not fullname.startswith("ginext."):
        return False
    sym = plugin.lookup_fully_qualified(fullname)
    if sym is None or not isinstance(sym.node, TypeInfo):
        return False
    return _is_native_gobject_type(sym.node)


class GinextPlugin(Plugin):
    def get_base_class_hook(
        self, fullname: str
    ) -> Callable[[ClassDefContext], None] | None:
        if _is_native_gobject_base(self, fullname):
            return check_native_gobject_class
        return None


def check_native_gobject_class(ctx: ClassDefContext) -> None:
    for stmt in ctx.cls.defs.body:
        if not isinstance(stmt, AssignmentStmt):
            continue
        if any(isinstance(lvalue, NameExpr) and lvalue.name == "__gtype_name__" for lvalue in stmt.lvalues):
            ctx.api.fail(
                "Do not set __gtype_name__ on native GObject classes; use class Foo(..., type_name=\"RegisteredTypeName\") instead.",
                stmt,
            )

    type_name = ctx.cls.keywords.get("type_name")
    if isinstance(type_name, StrExpr) and type_name.value == ctx.cls.name:
        ctx.api.fail(
            "type_name= must not be the same as the Python class name; pass the registered GType name instead.",
            type_name,
        )


def plugin(version: str) -> type[GinextPlugin]:
    return GinextPlugin
