from __future__ import annotations

from pathlib import Path

from ginext import Gtk

_BUILDER_DIR = Path(__file__).resolve().parent


def load_builder(name: str) -> Gtk.Builder:
    builder = Gtk.Builder()
    builder.add_from_string((_BUILDER_DIR / name).read_text(), -1)
    return builder


def get_widget[T](builder: Gtk.Builder, name: str, widget_type: type[T]) -> T:
    widget = builder.get_object(name)
    if not isinstance(widget, widget_type):
        raise RuntimeError(f"Builder object {name!r} is not a {widget_type.__name__}")
    return widget
