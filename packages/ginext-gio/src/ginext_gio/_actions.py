# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ParamSpec, TypeVar, cast

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from ginext import Gio


_ACTION_METADATA_ATTR = "gimeta_action"
_ACTION_BUCKET_KEY = "actions"
_P = ParamSpec("_P")
R = TypeVar("R")


@dataclass(slots=True, frozen=True)
class ActionSpec:
    attr_name: str
    name: str
    accels: tuple[str, ...]


def action(
    name: str, accels: Sequence[str] | None = None
) -> Callable[[Callable[_P, R]], Callable[_P, R]]:
    def decorate(fn: Callable[_P, R]) -> Callable[_P, R]:
        setattr(
            fn,
            _ACTION_METADATA_ATTR,
            ActionSpec(
                attr_name=getattr(fn, "__name__", ""),
                name=name,
                accels=tuple(accels or ()),
            ),
        )
        return fn

    return decorate


def _gtk_bucket(owner: object) -> dict[str, object] | None:
    gimeta = getattr(owner, "gimeta", None)
    if gimeta is None:
        return None
    extensions = getattr(gimeta, "extensions", None)
    if not isinstance(extensions, dict):
        return None
    bucket = extensions.get("Gtk")
    if isinstance(bucket, dict):
        return cast("dict[str, object]", bucket)
    return None


def install_application_actions(app: Gio.Application) -> None:
    from ginext import Gio

    specs_by_name: dict[str, ActionSpec] = {}
    for cls in reversed(type(app).__mro__):
        bucket = _gtk_bucket(cls)
        if bucket is None:
            continue
        specs = bucket.get(_ACTION_BUCKET_KEY, ())
        if not isinstance(specs, list):
            continue
        for spec in specs:
            if isinstance(spec, ActionSpec):
                specs_by_name[spec.name] = spec

    for spec in specs_by_name.values():
        handler = getattr(app, spec.attr_name)
        action = Gio.ActionMap.lookup_action(app, spec.name)
        if action is None:
            simple = Gio.SimpleAction.new(spec.name, None)
            simple.activate.connect(handler, owner=app)
            Gio.ActionMap.add_action(app, simple)
        if spec.accels and hasattr(app, "set_accels_for_action"):
            app.set_accels_for_action(f"app.{spec.name}", list(spec.accels))
