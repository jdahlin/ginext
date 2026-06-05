"""Adwaita settings window for the browser example."""

from __future__ import annotations

from pathlib import Path

from goi.repository import Adw, GObject, Gtk


Adw.init()
_ = (Adw.PreferencesWindow, Adw.PreferencesPage, Adw.PreferencesGroup, Adw.SwitchRow)

_UI = (Path(__file__).resolve().parent / "resources" / "settings.ui").read_text()


@Gtk.Template(string=_UI)
class SettingsWindow(Gtk.Window):
    __gtype_name__ = "WebBrowserSettings"

    developer_extras_row = Gtk.Template.Child()
    javascript_row = Gtk.Template.Child()
    webgl_row = Gtk.Template.Child()
    webrtc_row = Gtk.Template.Child()
    media_stream_row = Gtk.Template.Child()
    page_cache_row = Gtk.Template.Child()
    dns_prefetching_row = Gtk.Template.Child()
    smooth_scrolling_row = Gtk.Template.Child()
    tabs_to_links_row = Gtk.Template.Child()
    clipboard_access_row = Gtk.Template.Child()
    popup_windows_row = Gtk.Template.Child()
    print_backgrounds_row = Gtk.Template.Child()
    media_autoplay_row = Gtk.Template.Child()
    itp_row = Gtk.Template.Child()
    persistent_credentials_row = Gtk.Template.Child()
    third_party_cookies_row = Gtk.Template.Child()

    def __init__(self, state):
        super().__init__()
        self.state = state
        flags = GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.BIDIRECTIONAL
        for key, row in (
            ("developer-extras", self.developer_extras_row),
            ("javascript", self.javascript_row),
            ("webgl", self.webgl_row),
            ("webrtc", self.webrtc_row),
            ("media-stream", self.media_stream_row),
            ("page-cache", self.page_cache_row),
            ("dns-prefetching", self.dns_prefetching_row),
            ("smooth-scrolling", self.smooth_scrolling_row),
            ("tabs-to-links", self.tabs_to_links_row),
            ("clipboard-access", self.clipboard_access_row),
            ("popup-windows", self.popup_windows_row),
            ("print-backgrounds", self.print_backgrounds_row),
            ("media-autoplay", self.media_autoplay_row),
            ("itp", self.itp_row),
            ("persistent-credentials", self.persistent_credentials_row),
            ("third-party-cookies", self.third_party_cookies_row),
        ):
            state.bind_property(key, row, "active", flags)
