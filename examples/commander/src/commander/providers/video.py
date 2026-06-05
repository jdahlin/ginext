from __future__ import annotations

from ginext import Gio, Gtk

from commander.fs import File
from commander.providers.base import CommanderProviderContext, ProviderCapability


class VideoProvider:
    id = "video"
    label = "Video"
    priority = 70
    capabilities = (ProviderCapability.QUICK_VIEW,)

    def supports(
        self,
        file: File,
        info: Gio.FileInfo,
        context: CommanderProviderContext,
    ) -> bool:
        content_type = info.get_content_type() or ""
        return content_type.startswith("video/") or content_type.startswith("audio/")

    def create_widget(
        self,
        file: File,
        info: Gio.FileInfo,
        context: CommanderProviderContext,
    ) -> Gtk.Widget:
        label = Gtk.Label(xalign=0.0, yalign=0.0)
        label.set_wrap(True)
        label.set_text("Video quick view provider requires GStreamer integration")
        return label
