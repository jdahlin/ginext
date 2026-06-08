"""Adw.Application subclass — owns the window factory.

App-level actions:
  - app.new-window     (Ctrl+N): spawn another Window
  - app.about:                   open AdwAboutWindow
  - app.quit           (Ctrl+Q): close all windows
"""

from __future__ import annotations

import os
import signal
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ginext import Adw, Gio, GLib, GLibUnix, Gtk, defaults

# WebKit ships both 4.x (WebKit2) and 6.0; pin the GTK 4 build before
# the namespace is imported.
defaults.require("WebKit", "6.0")

from ginext import WebKit  # noqa: E402

from examples.web_browser.extensions import ExtensionRegistry
from examples.web_browser.state import BrowserState
from examples.web_browser.store import Store
from examples.web_browser.window import Window


_APP_ID = "org.ginext.WebBrowser"
_PROFILE_NAME = "ginext-web-browser"


def _enum_member(enum: Any, *names: str, default: Any) -> Any:
    for name in names:
        value = getattr(enum, name, None)
        if value is not None:
            return value
    return default


_DownloadCallback = Callable[[bool, str | None], None]


def _xdg_dir(env_name: str, fallback: Path) -> Path:
    value = os.environ.get(env_name)
    if value:
        return Path(value)
    return fallback


class App(Gtk.Application, type_name="WebBrowserApp"):
    """Gtk.Application + Adw.init() — same shape as pyedit's App."""

    def __init__(self) -> None:
        super().__init__(
            application_id=_APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self._sigint_handle = 0
        self.state = BrowserState()
        self.store = Store()
        self.extensions = ExtensionRegistry()
        self._downloads: list[WebKit.Download] = []
        self.web_context: WebKit.WebContext | None = None
        self.network_session: WebKit.NetworkSession | None = None
        self.website_data_manager: WebKit.WebsiteDataManager | None = None
        self.cookie_manager: WebKit.CookieManager | None = None
        self.profile_data_dir: Path | None = None
        self.profile_cache_dir: Path | None = None

    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        Adw.init()
        self._configure_webkit_profile()
        # The new API has no all-properties "notify" connect: wire one
        # per-property notify for every settings key.
        for key in BrowserState._KEYS:
            self.state.notify(key).connect(self._on_settings_changed)
        self.extensions.start(WebKit, Gio)
        self._install_actions()
        self._install_sigint_handler()

    def _configure_webkit_profile(self) -> None:
        data_root = _xdg_dir("XDG_DATA_HOME", Path.home() / ".local" / "share")
        cache_root = _xdg_dir("XDG_CACHE_HOME", Path.home() / ".cache")
        self.profile_data_dir = data_root / _PROFILE_NAME / "webkit"
        self.profile_cache_dir = cache_root / _PROFILE_NAME / "webkit"
        self.profile_data_dir.mkdir(parents=True, exist_ok=True)
        self.profile_cache_dir.mkdir(parents=True, exist_ok=True)

        self.web_context = WebKit.WebContext.get_default()
        cache_model = _enum_member(
            WebKit.CacheModel, "WEB_BROWSER", "web_browser", default=1
        )
        self.web_context.set_cache_model(cache_model)
        if hasattr(self.web_context, "set_spell_checking_enabled"):
            self.web_context.set_spell_checking_enabled(True)
        self._register_browser_scheme()

        self.network_session = WebKit.NetworkSession.new(
            str(self.profile_data_dir),
            str(self.profile_cache_dir),
        )
        self.network_session.download_started.connect(self._on_download_started)

        tls_policy = _enum_member(WebKit.TLSErrorsPolicy, "FAIL", "fail", default=1)
        self.network_session.set_tls_errors_policy(tls_policy)
        self.network_session.set_itp_enabled(self.state.itp)
        self.network_session.set_persistent_credential_storage_enabled(
            self.state.persistent_credentials
        )

        self.website_data_manager = self.network_session.get_website_data_manager()
        self.website_data_manager.set_favicons_enabled(True)

        self.cookie_manager = self.network_session.get_cookie_manager()
        storage = _enum_member(
            WebKit.CookiePersistentStorage, "SQLITE", "sqlite", default=1
        )
        policy = self._cookie_policy()
        self.cookie_manager.set_persistent_storage(
            str(self.profile_data_dir / "cookies.sqlite"),
            storage,
        )
        self.cookie_manager.set_accept_policy(policy)

    def _register_browser_scheme(self) -> None:
        assert self.web_context is not None
        try:
            self.web_context.register_uri_scheme(  # type: ignore[call-arg]  # stub mismodels register_uri_scheme user_data/destroy args
                "browser",
                self._on_browser_scheme_request,
                None,
                None,
            )
        except Exception:
            pass
        manager = self.web_context.get_security_manager()
        for method in (
            "register_uri_scheme_as_secure",
            "register_uri_scheme_as_cors_enabled",
            "register_uri_scheme_as_display_isolated",
        ):
            if hasattr(manager, method):
                getattr(manager, method)("browser")

    def _on_browser_scheme_request(self, request: Any, *_a: object) -> None:
        uri = request.get_uri() if hasattr(request, "get_uri") else "browser://"
        path = (request.get_path() if hasattr(request, "get_path") else "") or ""
        if path in ("", "/", "settings"):
            body = self._browser_settings_page()
        else:
            body = (
                f"<h1>browser://{path}</h1><p>No page is registered for this path.</p>"
            )
        data = body.encode("utf-8")
        stream = Gio.MemoryInputStream.new_from_bytes(GLib.Bytes.new(data))  # type: ignore[arg-type]  # stub mismodels new_from_bytes as bytes instead of GLib.Bytes
        request.finish(stream, len(data), "text/html")
        print(f"[web-browser] served {uri}", file=sys.stderr)

    def _browser_settings_page(self) -> str:
        return """<!doctype html>
<meta charset="utf-8">
<title>Browser Settings</title>
<style>
body {{ font: 15px system-ui, sans-serif; margin: 2rem; max-width: 760px; }}
dt {{ font-weight: 700; margin-top: 1rem; }}
dd {{ margin: .25rem 0 0; }}
</style>
<h1>Browser Settings</h1>
<p>This internal page is served through WebKit's registered URI-scheme hook.</p>
<dl>
<dt>Profile data</dt><dd>{data}</dd>
<dt>Profile cache</dt><dd>{cache}</dd>
<dt>Intelligent Tracking Prevention</dt><dd>{itp}</dd>
<dt>Third-party cookies</dt><dd>{third_party}</dd>
<dt>JavaScript</dt><dd>{javascript}</dd>
</dl>
""".format(
            data=self.profile_data_dir,
            cache=self.profile_cache_dir,
            itp=self.state.itp,
            third_party=self.state.third_party_cookies,
            javascript=self.state.javascript,
        )

    def _on_settings_changed(self, *_a: object) -> None:
        if self.network_session is not None:
            self.network_session.set_itp_enabled(self.state.itp)
            self.network_session.set_persistent_credential_storage_enabled(
                self.state.persistent_credentials
            )
        if self.cookie_manager is not None:
            self.cookie_manager.set_accept_policy(self._cookie_policy())
        self.apply_settings_to_views()

    def _cookie_policy(self) -> Any:
        if self.state.third_party_cookies:
            return _enum_member(
                WebKit.CookieAcceptPolicy, "ALWAYS", "always", default=0
            )
        return _enum_member(
            WebKit.CookieAcceptPolicy, "NO_THIRD_PARTY", "no_third_party", default=2
        )

    def apply_settings_to_views(self) -> None:
        for window in self.get_windows():
            tab_view = getattr(window, "tab_view", None)
            if tab_view is None:
                continue
            for index in range(tab_view.get_n_pages()):
                page = tab_view.get_nth_page(index)
                if page is not None:
                    self.apply_settings_to_view(page.get_child())

    def apply_settings_to_view(self, view: WebKit.WebView) -> None:
        settings = view.get_settings()
        mapping: dict[str, object] = {
            "set_enable_developer_extras": self.state.developer_extras,
            "set_enable_fullscreen": True,
            "set_enable_html5_database": True,
            "set_enable_html5_local_storage": True,
            "set_enable_javascript": self.state.javascript,
            "set_enable_media_stream": self.state.media_stream,
            "set_enable_page_cache": self.state.page_cache,
            "set_enable_smooth_scrolling": self.state.smooth_scrolling,
            "set_enable_tabs_to_links": self.state.tabs_to_links,
            "set_enable_webaudio": True,
            "set_enable_webgl": self.state.webgl,
            "set_enable_webrtc": self.state.webrtc,
            "set_javascript_can_access_clipboard": self.state.clipboard_access,
            "set_javascript_can_open_windows_automatically": self.state.popup_windows,
            "set_media_playback_allows_inline": True,
            "set_print_backgrounds": self.state.print_backgrounds,
        }
        for setter, value in mapping.items():
            if hasattr(settings, setter):
                getattr(settings, setter)(value)
        if hasattr(settings, "set_media_playback_requires_user_gesture"):
            settings.set_media_playback_requires_user_gesture(
                not self.state.media_autoplay
            )

    def clear_website_data(self, callback: _DownloadCallback) -> None:
        if self.website_data_manager is None:
            callback(False, "Website data manager is not available")
            return
        data_types = _enum_member(WebKit.WebsiteDataTypes, "ALL", "all", default=4095)
        self.website_data_manager.clear(  # type: ignore[call-arg]  # stub mismodels WebKit async callback (GAsyncReadyCallback + user_data)
            data_types,
            0,
            None,
            self._on_clear_website_data_done,  # type: ignore[arg-type]  # stub mismodels WebKit async callback signature
            callback,
        )

    def _on_clear_website_data_done(
        self, manager: Any, result: Any, callback: _DownloadCallback
    ) -> None:
        try:
            callback(bool(manager.clear_finish(result)), None)
        except Exception as exc:
            callback(False, str(exc))

    def fetch_website_data_summary(self, callback: _DownloadCallback) -> None:
        if self.website_data_manager is None:
            callback(False, "Website data manager is not available")
            return
        data_types = _enum_member(WebKit.WebsiteDataTypes, "ALL", "all", default=4095)
        self.website_data_manager.fetch(  # type: ignore[call-arg]  # stub mismodels WebKit async callback (GAsyncReadyCallback + user_data)
            data_types,
            None,
            self._on_website_data_fetched,  # type: ignore[arg-type]  # stub mismodels WebKit async callback signature
            callback,
        )

    def _on_website_data_fetched(
        self, manager: Any, result: Any, callback: _DownloadCallback
    ) -> None:
        try:
            entries = list(manager.fetch_finish(result) or [])
        except Exception as exc:
            callback(False, str(exc))
            return
        if not entries:
            callback(True, "No website data")
            return
        names = []
        data_types = _enum_member(WebKit.WebsiteDataTypes, "ALL", "all", default=4095)
        for entry in entries[:8]:
            name = entry.get_name() if hasattr(entry, "get_name") else str(entry)
            size = entry.get_size(data_types) if hasattr(entry, "get_size") else 0
            names.append(f"{name} ({GLib.format_size(size)})")
        suffix = "" if len(entries) <= 8 else f", +{len(entries) - 8} more"
        callback(True, "Website data: " + ", ".join(names) + suffix)

    def fetch_cookie_summary(self, callback: _DownloadCallback) -> None:
        if self.cookie_manager is None or not hasattr(
            self.cookie_manager, "get_all_cookies"
        ):
            callback(False, "Cookie manager cannot list cookies")
            return
        self.cookie_manager.get_all_cookies(None, self._on_cookies_fetched, callback)  # type: ignore[call-arg, arg-type]  # stub mismodels WebKit async callback (GAsyncReadyCallback + user_data)

    def _on_cookies_fetched(
        self, manager: Any, result: Any, callback: _DownloadCallback
    ) -> None:
        try:
            cookies = list(manager.get_all_cookies_finish(result) or [])
        except Exception as exc:
            callback(False, str(exc))
            return
        if not cookies:
            callback(True, "No cookies")
            return
        names = []
        for cookie in cookies[:8]:
            if hasattr(cookie, "get_name"):
                names.append(cookie.get_name())
            else:
                names.append(str(cookie).split("=", 1)[0])
        suffix = "" if len(cookies) <= 8 else f", +{len(cookies) - 8} more"
        callback(True, "Cookies: " + ", ".join(names) + suffix)

    def page_archive_destination(self, title: str) -> Path:
        downloads = Path.home() / "Downloads"
        downloads.mkdir(parents=True, exist_ok=True)
        safe = "".join(
            ch if ch.isalnum() or ch in "._- " else "_" for ch in title
        ).strip()
        safe = safe or "page"
        candidate = downloads / f"{safe}.mhtml"
        if not candidate.exists():
            return candidate
        for index in range(1, 1000):
            numbered = downloads / f"{safe}-{index}.mhtml"
            if not numbered.exists():
                return numbered
        return downloads / f"{safe}-{GLib.get_monotonic_time()}.mhtml"

    def _install_sigint_handler(self) -> None:
        try:
            self._sigint_handle = GLibUnix.signal_add(
                GLib.PRIORITY_DEFAULT,
                signal.SIGINT,
                self._on_sigint,
            )
        except AttributeError:
            signal.signal(signal.SIGINT, lambda *_: self.quit())

    def _on_sigint(self, *_a: object) -> bool:
        print("\n[web-browser] caught SIGINT, quitting", file=sys.stderr)
        self.quit()
        return False

    def do_activate(self) -> None:
        existing = self.get_active_window()
        if existing is None:
            win = self.spawn_window(present=True)
            win.new_tab()
        else:
            existing.present()

    def do_command_line(self, cmdline: Gio.ApplicationCommandLine) -> int:
        argv = cmdline.get_arguments() or []
        uris = [a for a in argv[1:] if not a.startswith("-")]
        if not uris:
            self.activate()
            return 0
        active = self.get_active_window()
        win = active if isinstance(active, Window) else self.spawn_window(present=False)
        for uri in uris:
            win.new_tab(uri)
        win.present()
        return 0

    def spawn_window(self, *, present: bool) -> Window:
        win = Window(application=self, store=self.store)
        if present:
            win.present()
        return win

    _APP_ACTIONS: tuple[tuple[str, str, list[str] | None], ...] = (
        ("new-window", "_on_new_window", ["<Primary>n"]),
        ("about", "_on_about", None),
        ("quit", "_on_quit", ["<Primary>q"]),
    )

    def _install_actions(self) -> None:
        for name, handler, accels in self._APP_ACTIONS:
            action = Gio.SimpleAction.new(name, None)
            action.activate.connect(getattr(self, handler))
            self.add_action(action)
            if accels:
                self.set_accels_for_action(f"app.{name}", list(accels))

    def _on_new_window(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        win = self.spawn_window(present=True)
        win.new_tab()

    def _on_about(self, _action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        about = Adw.AboutWindow(
            transient_for=self.get_active_window(),
            application_name="Web Browser",
            application_icon="web-browser-symbolic",
            developer_name="ginext",
            version="0.0.0",
            comments="An epiphany-shaped showcase for ginext.",
            website="https://github.com/jdahlin/ginext",
            license_type=Gtk.License.MIT_X11,
        )
        about.present()

    def _on_quit(self, _action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        for w in list(self.get_windows()):
            w.close()

    # ------------------------------------------------------------------
    # Downloads
    # ------------------------------------------------------------------
    def _on_download_started(
        self, _context: WebKit.NetworkSession, download: WebKit.Download
    ) -> None:
        self._downloads.append(download)
        download.decide_destination.connect(self._on_download_decide_destination)
        download.created_destination.connect(self._on_download_created_destination)
        download.failed.connect(self._on_download_failed)
        download.finished.connect(self._on_download_finished)
        self._toast_active_window("Download started")

    def _on_download_decide_destination(
        self, download: WebKit.Download, suggested_filename: str
    ) -> bool:
        destination = self._download_destination(suggested_filename or "download")
        download.set_allow_overwrite(False)
        download.set_destination(destination.resolve().as_uri())
        return True

    def _on_download_created_destination(
        self, _download: WebKit.Download, destination: str
    ) -> None:
        self._toast_active_window(
            f"Saving {self._display_download_destination(destination)}"
        )

    def _on_download_failed(
        self, download: WebKit.Download, error: GLib.Error
    ) -> None:
        self._forget_download(download)
        message = getattr(error, "message", str(error))
        self._toast_active_window(f"Download failed: {message}")

    def _on_download_finished(self, download: WebKit.Download) -> None:
        destination = download.get_destination() or ""
        self._forget_download(download)
        if destination:
            self._toast_active_window(
                f"Downloaded {self._display_download_destination(destination)}"
            )
        else:
            self._toast_active_window("Download finished")

    def _forget_download(self, download: WebKit.Download) -> None:
        try:
            self._downloads.remove(download)
        except ValueError:
            pass

    def _download_destination(self, suggested_filename: str) -> Path:
        downloads = Path.home() / "Downloads"
        downloads.mkdir(parents=True, exist_ok=True)
        safe = Path(suggested_filename).name or "download"
        candidate = downloads / safe
        if not candidate.exists():
            return candidate
        stem = candidate.stem or "download"
        suffix = candidate.suffix
        for index in range(1, 1000):
            numbered = downloads / f"{stem}-{index}{suffix}"
            if not numbered.exists():
                return numbered
        return downloads / f"{stem}-{GLib.get_monotonic_time()}{suffix}"

    @staticmethod
    def _display_download_destination(destination: str) -> str:
        if destination.startswith("file://"):
            return Gio.File.new_for_uri(destination).get_basename() or destination
        return Path(destination).name or destination

    def _toast_active_window(self, text: str) -> None:
        win = self.get_active_window()
        if isinstance(win, Window):
            win._toast(text)
