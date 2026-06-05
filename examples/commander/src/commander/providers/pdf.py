from __future__ import annotations

import cairo
from ginext import Gio, GLib, Gtk, Poppler

from commander.components.quickview import ZoomableQuickView
from commander.fs import File
from commander.providers.base import CommanderProviderContext, ProviderCapability

PAGE_GAP = 12
PAGE_MARGIN = 10
MAX_PAGES = 128


class PdfProvider:
    id = "pdf"
    label = "PDF"
    priority = 80
    capabilities = (ProviderCapability.QUICK_VIEW,)

    def __init__(self) -> None:
        self._zoom_by_uri: dict[str, float] = {}

    def supports(
        self,
        file: File,
        info: Gio.FileInfo,
        context: CommanderProviderContext,
    ) -> bool:
        content_type = info.get_content_type() or ""
        return Gio.content_type_is_mime_type(content_type, "application/pdf")

    def create_widget(
        self,
        file: File,
        info: Gio.FileInfo,
        context: CommanderProviderContext,
    ) -> Gtk.Widget:
        uri = file.uri or file.parse_name or ""
        try:
            return ZoomableQuickView(
                PdfContent(file),
                initial_zoom=self._zoom_by_uri.get(uri, 1.0),
                on_zoom_changed=lambda zoom: self._remember_zoom(uri, zoom),
            )
        except GLib.Error as error:
            label = Gtk.Label(label=f"Unable to load PDF: {error.message}", xalign=0.0)
            label.set_wrap(True)
            return label

    def _remember_zoom(self, uri: str, zoom: float) -> None:
        if uri:
            self._zoom_by_uri[uri] = zoom


class PdfContent(Gtk.DrawingArea, type_name="GoiCommanderPdfContent"):

    def __init__(self, file: File) -> None:
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.document = Poppler.Document.new_from_file(file.uri, None)
        self.pages = self._load_pages()
        self.base_width = self._content_width()
        self.base_height = self._content_height()
        self.zoom = 1.0
        self.add_css_class("quick-view-pdf")
        self.set_draw_func(self._draw)

    def _load_pages(self) -> list[tuple[Poppler.Page, int, int]]:
        pages: list[tuple[Poppler.Page, int, int]] = []
        n_pages = min(self.document.get_n_pages(), MAX_PAGES)
        for index in range(n_pages):
            page = self.document.get_page(index)
            size = page.get_size()
            pages.append((page, int(size.width), int(size.height)))
        return pages

    def _content_width(self) -> int:
        if not self.pages:
            return PAGE_MARGIN * 2
        return max(width for _page, width, _height in self.pages) + PAGE_MARGIN * 2

    def _content_height(self) -> int:
        if not self.pages:
            return PAGE_MARGIN * 2
        page_height = sum(height for _page, _width, height in self.pages)
        gaps = PAGE_GAP * max(0, len(self.pages) - 1)
        return page_height + gaps + PAGE_MARGIN * 2

    def _draw(
        self,
        _area: Gtk.DrawingArea,
        cr: cairo.Context[cairo.Surface],
        _width: int,
        _height: int,
    ) -> None:
        cr.set_source_rgb(0.74, 0.74, 0.74)
        cr.paint()

        cr.save()
        cr.scale(self.zoom, self.zoom)
        y = PAGE_MARGIN
        for page, page_width, page_height in self.pages:
            cr.save()
            cr.translate(PAGE_MARGIN, y)
            cr.set_source_rgb(1, 1, 1)
            cr.rectangle(0, 0, page_width, page_height)
            cr.fill()
            page.render_for_printing(cr)
            cr.restore()
            y += page_height + PAGE_GAP
        cr.restore()

    def set_zoom(self, zoom: float) -> None:
        self.zoom = zoom
        self.set_content_width(max(1, int(self.base_width * zoom)))
        self.set_content_height(max(1, int(self.base_height * zoom)))
        self.set_size_request(
            max(1, int(self.base_width * zoom)),
            max(1, int(self.base_height * zoom)),
        )
        self.queue_draw()
