from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from ginext import Gdk, Gtk

DEFAULT_ZOOM_STEP = 1.15
DEFAULT_MIN_ZOOM = 0.05
DEFAULT_MAX_ZOOM = 16.0


class ZoomableQuickView(Gtk.Box, type_name="GoiCommanderZoomableQuickView"):

    def __init__(
        self,
        content: Gtk.Widget,
        *,
        initial_zoom: float = 1.0,
        min_zoom: float = DEFAULT_MIN_ZOOM,
        max_zoom: float = DEFAULT_MAX_ZOOM,
        zoom_step: float = DEFAULT_ZOOM_STEP,
        on_zoom_changed: Callable[[float], None] | None = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.content = content
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom
        self.zoom_step = zoom_step
        self.zoom = self._clamp(initial_zoom)
        self._on_zoom_changed = on_zoom_changed

        self.content.set_halign(Gtk.Align.START)
        self.content.set_valign(Gtk.Align.START)

        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scroller.set_hexpand(True)
        self.scroller.set_vexpand(True)
        if hasattr(self.scroller, "set_propagate_natural_width"):
            self.scroller.set_propagate_natural_width(False)
        if hasattr(self.scroller, "set_propagate_natural_height"):
            self.scroller.set_propagate_natural_height(False)
        self.scroller.set_child(self.content)

        scroll_flags = (
            Gtk.EventControllerScrollFlags.VERTICAL | Gtk.EventControllerScrollFlags.HORIZONTAL
        )
        controller = Gtk.EventControllerScroll.new(scroll_flags)
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        controller.scroll.connect(self._on_scroll)
        self.scroller.add_controller(controller)

        self.append(self.scroller)
        self._apply_zoom(remember=False)

    def _on_scroll(
        self,
        controller: Gtk.EventControllerScroll,
        dx: float,
        dy: float,
    ) -> bool:
        state = self._current_event_state(controller)
        if not state & Gdk.ModifierType.SHIFT_MASK:
            return False
        delta = dy if dy else dx
        if delta < 0:
            self.set_zoom(self.zoom * self.zoom_step)
        elif delta > 0:
            self.set_zoom(self.zoom / self.zoom_step)
        return True

    def _current_event_state(self, controller: Gtk.EventControllerScroll) -> Gdk.ModifierType:
        event = controller.get_current_event()
        if event is not None:
            return event.get_modifier_state()
        return controller.get_current_event_state()

    def set_zoom(self, zoom: float) -> None:
        clamped = self._clamp(zoom)
        if abs(clamped - self.zoom) < 0.001:
            return
        self.zoom = clamped
        self._apply_zoom(remember=True)

    def _apply_zoom(self, *, remember: bool) -> None:
        cast(Any, self.content).set_zoom(self.zoom)
        if remember and self._on_zoom_changed is not None:
            self._on_zoom_changed(self.zoom)

    def _clamp(self, zoom: float) -> float:
        return max(self.min_zoom, min(self.max_zoom, zoom))
