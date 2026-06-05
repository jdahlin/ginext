from __future__ import annotations

from ginext import Gdk, GdkPixbuf, Gio, GLib, Gtk

from commander.components.quickview import ZoomableQuickView
from commander.fs import File
from commander.providers.base import CommanderProviderContext, ProviderCapability


class ImageProvider:
    id = "image"
    label = "Image"
    priority = 90
    capabilities = (ProviderCapability.QUICK_VIEW,)

    def __init__(self) -> None:
        self._zoom_by_uri: dict[str, float] = {}

    def supports(
        self,
        file: File,
        info: Gio.FileInfo,
        context: CommanderProviderContext,
    ) -> bool:
        return (info.get_content_type() or "").startswith("image/")

    def create_widget(
        self,
        file: File,
        info: Gio.FileInfo,
        context: CommanderProviderContext,
    ) -> Gtk.Widget:
        uri = file.uri or file.parse_name or ""
        try:
            return ZoomableQuickView(
                ImageContent(file),
                initial_zoom=self._zoom_by_uri.get(uri, 1.0),
                on_zoom_changed=lambda zoom: self._remember_zoom(uri, zoom),
            )
        except GLib.Error as error:
            label = Gtk.Label(label=f"Unable to load image: {error.message}", xalign=0.0)
            label.set_wrap(True)
            return label

    def _remember_zoom(self, uri: str, zoom: float) -> None:
        if uri:
            self._zoom_by_uri[uri] = zoom


class ImageContent(Gtk.Picture, type_name="GoiCommanderImageContent"):

    def __init__(self, file: File) -> None:
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.pixbuf: GdkPixbuf.Pixbuf = _load_pixbuf(file)
        self.scaled_pixbuf: GdkPixbuf.Pixbuf | None = None
        self.set_can_shrink(False)
        self.set_keep_aspect_ratio(True)

    def set_zoom(self, zoom: float) -> None:
        width = max(1, int(self.pixbuf.get_width() * zoom))
        height = max(1, int(self.pixbuf.get_height() * zoom))
        if abs(zoom - 1.0) < 0.001:
            self.scaled_pixbuf = self.pixbuf
        else:
            self.scaled_pixbuf = self.pixbuf.scale_simple(
                width,
                height,
                GdkPixbuf.InterpType.BILINEAR,
            )
        assert self.scaled_pixbuf is not None
        texture = Gdk.Texture.new_for_pixbuf(self.scaled_pixbuf)
        self.set_paintable(texture)
        self.set_size_request(width, height)


def _load_pixbuf(file: File) -> GdkPixbuf.Pixbuf:
    stream = file.read_stream()
    try:
        return GdkPixbuf.Pixbuf.new_from_stream(stream, None)
    finally:
        stream.close(None)
