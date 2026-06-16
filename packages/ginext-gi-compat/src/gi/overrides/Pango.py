from __future__ import annotations

from gi.repository import Pango as _Pango

__all__: list[str] = []

_Layout = _Pango.Layout
_raw_set_markup = _Layout.set_markup
_raw_set_text = _Layout.set_text


def _remove_from_method_infos(cls: type, name: str) -> None:
    try:
        from ginext.gobject.resolve import own_gimeta
        for owner in cls.__mro__:
            gimeta = own_gimeta(owner)
            if gimeta is None:
                continue
            gimeta.remove_method(name)
    except Exception:
        pass


_raw_layout_new_factory = _Layout.new


def _layout_new(cls, context=None):
    if context is None:
        raise TypeError(
            "Pango.Layout requires a Pango.Context argument"
        )
    return _raw_layout_new_factory(context)


def _layout_init(self, context=None):
    pass


_Layout.__new__ = _layout_new
_Layout.__init__ = _layout_init
_remove_from_method_infos(_Layout, "__new__")
_remove_from_method_infos(_Layout, "__init__")


def _layout_set_markup(self, markup, length=-1):
    if length == -1:
        length = len(markup.encode("utf-8"))
    _raw_set_markup(self, markup, length)


def _layout_set_text(self, text, length=-1):
    if length == -1:
        length = len(text.encode("utf-8"))
    _raw_set_text(self, text, length)


_Layout.set_markup = _layout_set_markup
_Layout.set_text = _layout_set_text
_remove_from_method_infos(_Layout, "set_markup")
_remove_from_method_infos(_Layout, "set_text")
