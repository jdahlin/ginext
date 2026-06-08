"""Adwaita settings window for the browser example."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ginext import Adw, GObject, Gtk

if TYPE_CHECKING:
    from examples.web_browser.state import BrowserState


Adw.init()
_ = (Adw.PreferencesWindow, Adw.PreferencesPage, Adw.PreferencesGroup, Adw.SwitchRow)

_UI = (Path(__file__).resolve().parent / "resources" / "settings.ui").read_text()


@Gtk.Template(string=_UI)
class SettingsWindow(Gtk.Window, type_name="WebBrowserSettings"):

    developer_extras_row: Adw.SwitchRow
    javascript_row: Adw.SwitchRow
    webgl_row: Adw.SwitchRow
    webrtc_row: Adw.SwitchRow
    media_stream_row: Adw.SwitchRow
    page_cache_row: Adw.SwitchRow
    smooth_scrolling_row: Adw.SwitchRow
    tabs_to_links_row: Adw.SwitchRow
    clipboard_access_row: Adw.SwitchRow
    popup_windows_row: Adw.SwitchRow
    print_backgrounds_row: Adw.SwitchRow
    media_autoplay_row: Adw.SwitchRow
    itp_row: Adw.SwitchRow
    persistent_credentials_row: Adw.SwitchRow
    third_party_cookies_row: Adw.SwitchRow

    def __init__(self, state: BrowserState) -> None:
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
