"""Main window — Adw.ApplicationWindow with address bar, tabbed WebKit views,
history, bookmarks, security indicator, and inspector hookup.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import quote, urlparse

from ginext import Adw, Gio, GLib, GObject, Gtk, WebKit

if TYPE_CHECKING:
    from examples.web_browser.app import App
    from examples.web_browser.store import Store


_UI_DIR = Path(__file__).resolve().parent / "resources"
_WINDOW_UI = (_UI_DIR / "window.ui").read_text()
_MENUS_UI = str(_UI_DIR / "menus.ui")

HOMEPAGE = "https://www.gnome.org/"
SEARCH_URL = "https://duckduckgo.com/?q={}"

# Menu cap — surface the most-recent N. The full lists live in Store.
HISTORY_MENU_LIMIT = 25
BOOKMARKS_MENU_LIMIT = 50
EXTERNAL_SCHEMES = {"mailto", "tel", "sms", "irc", "ircs", "magnet"}


def _enum_member(enum: Any, *names: str, default: Any) -> Any:
    for name in names:
        value = getattr(enum, name, None)
        if value is not None:
            return value
    return default


def looks_like_url(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if "://" in t or t.startswith(("about:", "data:")):
        return True
    head = t.split("/", 1)[0]
    if head == "localhost" or head.startswith("localhost:"):
        return True
    return "." in head and " " not in head


def normalize_address(text: str) -> str:
    t = text.strip()
    if not t:
        return ""
    if looks_like_url(t):
        if "://" not in t and not t.startswith(("about:", "data:")):
            return "http://" + t
        return t
    return SEARCH_URL.format(quote(t))


@Gtk.Template(string=_WINDOW_UI)
class Window(Adw.ApplicationWindow, type_name="WebBrowserWindow"):

    toast_overlay: Adw.ToastOverlay
    header_bar: Adw.HeaderBar
    address_entry: Gtk.Entry
    find_bar: Gtk.Box
    find_entry: Gtk.SearchEntry
    find_count_label: Gtk.Label
    find_prev_button: Gtk.Button
    find_next_button: Gtk.Button
    find_close_button: Gtk.Button
    back_button: Gtk.Button
    forward_button: Gtk.Button
    reload_button: Gtk.Button
    home_button: Gtk.Button
    new_tab_button: Gtk.Button
    bookmark_button: Gtk.ToggleButton
    history_button: Gtk.MenuButton
    primary_menu_button: Gtk.MenuButton
    tab_view: Adw.TabView
    tab_bar: Adw.TabBar
    progress_bar: Gtk.ProgressBar

    def __init__(self, application: App, store: Store) -> None:
        super().__init__(application=application)
        self.app = application
        self.store = store

        builder = Gtk.Builder.new_from_file(_MENUS_UI)
        self.primary_menu_button.set_menu_model(
            cast("Gio.MenuModel", builder.get_object("primary_menu"))
        )
        self.history_button.set_menu_model(
            cast("Gio.MenuModel", builder.get_object("history_menu"))
        )
        self._history_section = cast("Gio.Menu", builder.get_object("history_section"))
        self._history_dropdown_section = cast(
            "Gio.Menu", builder.get_object("history_dropdown_section")
        )
        self._bookmarks_section = cast(
            "Gio.Menu", builder.get_object("bookmarks_section")
        )

        # Refresh menus when shared state changes.
        self.store.history_changed.connect(self._on_history_changed)
        self.store.bookmarks_changed.connect(self._on_bookmarks_changed)

        self.tab_view.notify("selected-page").connect(self._on_selected_page_changed)
        self.tab_view.close_page.connect(self._on_close_page)
        self.tab_view.create_window.connect(self._on_create_window)

        self.address_entry.activate.connect(self._on_address_activate)
        self.find_entry.search_changed.connect(self._on_find_changed)
        self.find_entry.activate.connect(self._on_find_next)
        self.find_prev_button.clicked.connect(self._on_find_previous)
        self.find_next_button.clicked.connect(self._on_find_next)
        self.find_close_button.clicked.connect(self._on_find_close)

        self._install_actions()
        self._rebuild_history_menu()
        self._rebuild_bookmarks_menu()

    def _on_history_changed(self, _store: Store) -> None:
        self._rebuild_history_menu()

    def _on_bookmarks_changed(self, _store: Store) -> None:
        self._rebuild_bookmarks_menu()
        self._sync_bookmark_button()

    _WIN_ACTIONS: tuple[tuple[str, str, list[str] | None], ...] = (
        ("new-tab", "_on_new_tab", ["<Primary>t"]),
        ("close-tab", "_on_close_tab", ["<Primary>w"]),
        ("back", "_on_back", ["<Alt>Left"]),
        ("forward", "_on_forward", ["<Alt>Right"]),
        ("reload", "_on_reload", ["<Primary>r", "F5"]),
        (
            "reload-bypass-cache",
            "_on_reload_bypass_cache",
            ["<Primary><Shift>r", "<Primary>F5"],
        ),
        ("stop", "_on_stop", ["Escape"]),
        ("home", "_on_home", ["<Alt>Home"]),
        ("zoom-in", "_on_zoom_in", ["<Primary>plus", "<Primary>equal"]),
        ("zoom-out", "_on_zoom_out", ["<Primary>minus"]),
        ("zoom-reset", "_on_zoom_reset", ["<Primary>0"]),
        ("focus-address", "_on_focus_address", ["<Primary>l", "F6"]),
        ("find", "_on_find", ["<Primary>f"]),
        ("preferences", "_on_preferences", ["<Primary>comma"]),
        ("inspect", "_on_inspect", ["<Primary><Shift>i", "F12"]),
        ("print", "_on_print", ["<Primary>p"]),
        ("save-page", "_on_save_page", ["<Primary>s"]),
        ("toggle-mute", "_on_toggle_mute", None),
        ("terminate-web-process", "_on_terminate_web_process", None),
        ("extensions", "_on_extensions", None),
        ("reload-extensions", "_on_reload_extensions", None),
        ("cookies", "_on_cookies", None),
        ("website-data", "_on_website_data", None),
        ("clear-website-data", "_on_clear_website_data", None),
        ("next-tab", "_on_next_tab", ["<Primary>Page_Down"]),
        ("prev-tab", "_on_prev_tab", ["<Primary>Page_Up"]),
        ("clear-history", "_on_clear_history", None),
        ("clear-bookmarks", "_on_clear_bookmarks", None),
    )

    def _install_actions(self) -> None:
        group = Gio.SimpleActionGroup()
        for name, handler, accels in self._WIN_ACTIONS:
            action = Gio.SimpleAction.new(name, None)
            action.activate.connect(getattr(self, handler))
            group.add_action(action)
            if accels:
                self.app.set_accels_for_action(f"win.{name}", list(accels))

        # Stateful: bookmark toggle reflects whether the current URI is bookmarked.
        bookmark = Gio.SimpleAction.new_stateful(
            "bookmark", None, GLib.Variant.new_boolean(False)
        )
        bookmark.activate.connect(self._on_bookmark_toggle)
        group.add_action(bookmark)
        self.app.set_accels_for_action("win.bookmark", ["<Primary>d"])

        # Parameterized "load this URI" used by history/bookmark menu items.
        load_uri = Gio.SimpleAction.new("load-uri", GLib.VariantType.new("s"))
        load_uri.activate.connect(self._on_load_uri_action)
        group.add_action(load_uri)

        self.insert_action_group("win", group)

    # ------------------------------------------------------------------
    # Tab lifecycle
    # ------------------------------------------------------------------
    @property
    def current_view(self) -> WebKit.WebView | None:
        page = self.tab_view.get_selected_page()
        return cast("WebKit.WebView | None", page.get_child()) if page is not None else None

    def new_tab(self, uri: str | None = None) -> WebKit.WebView:
        manager = self.app.extensions.create_user_content_manager()
        view = self._new_web_view(manager)
        self.app.apply_settings_to_view(view)

        view.notify("uri").connect(self._on_view_uri_changed)
        view.notify("title").connect(self._on_view_title_changed)
        view.notify("estimated-load-progress").connect(self._on_progress_changed)
        view.notify("is-loading").connect(self._on_loading_changed)
        view.load_changed.connect(self._on_load_changed)
        view.load_failed.connect(self._on_load_failed)
        view.load_failed_with_tls_errors.connect(
            self._on_load_failed_with_tls_errors
        )
        view.authenticate.connect(self._on_authenticate)
        view.close.connect(self._on_view_close)
        view.context_menu.connect(self._on_context_menu)
        view.context_menu_dismissed.connect(self._on_context_menu_dismissed)
        view.create.connect(self._on_view_create)
        view.decide_policy.connect(self._on_decide_policy)
        view.insecure_content_detected.connect(self._on_insecure_content_detected)
        view.mouse_target_changed.connect(self._on_mouse_target_changed)
        view.permission_request.connect(self._on_permission_request)
        # `print` is a builtin; the signal lives under the `print` attribute.
        getattr(view, "print").connect(self._on_print_requested)
        view.query_permission_state.connect(self._on_query_permission_state)
        view.ready_to_show.connect(self._on_ready_to_show)
        view.resource_load_started.connect(self._on_resource_load_started)
        view.run_as_modal.connect(self._on_run_as_modal)
        view.run_color_chooser.connect(self._on_run_color_chooser)
        view.run_file_chooser.connect(self._on_run_file_chooser)
        view.script_dialog.connect(self._on_script_dialog)
        view.show_notification.connect(self._on_show_notification)
        view.show_option_menu.connect(self._on_show_option_menu)
        view.submit_form.connect(self._on_submit_form)
        view.user_message_received.connect(self._on_user_message_received)
        view.enter_fullscreen.connect(self._on_enter_fullscreen)
        view.leave_fullscreen.connect(self._on_leave_fullscreen)
        view.web_process_terminated.connect(self._on_web_process_terminated)
        view.notify("favicon").connect(self._on_view_favicon_changed)
        view.notify("is-muted").connect(self._on_view_muted_changed)
        view.notify("is-playing-audio").connect(self._on_view_playing_audio_changed)
        view.notify("theme-color").connect(self._on_view_theme_color_changed)

        find = view.get_find_controller()
        find.found_text.connect(self._on_found_text)
        find.failed_to_find_text.connect(self._on_failed_to_find_text)

        back_forward = view.get_back_forward_list()
        if back_forward is not None:
            back_forward.changed.connect(self._on_back_forward_list_changed)

        tab_page = self.tab_view.append(view)
        tab_page.set_title("New Tab")
        target = uri or HOMEPAGE
        view.load_uri(target)
        self.tab_view.set_selected_page(tab_page)
        return view

    def _new_web_view(
        self, manager: WebKit.UserContentManager | None
    ) -> WebKit.WebView:
        kwargs: dict[str, Any] = {}
        if getattr(self.app, "network_session", None) is not None:
            kwargs["network_session"] = self.app.network_session
        if manager is not None:
            kwargs["user_content_manager"] = manager
        if kwargs:
            try:
                return WebKit.WebView(**kwargs)
            except Exception:
                pass
        if manager is not None and hasattr(
            WebKit.WebView, "new_with_user_content_manager"
        ):
            return cast(
                "WebKit.WebView",
                WebKit.WebView.new_with_user_content_manager(manager),
            )
        return WebKit.WebView()

    def _on_close_page(self, view: Adw.TabView, tab_page: Adw.TabPage) -> bool:
        # AdwTabView spec: returning TRUE means "I will finish this".
        # Returning FALSE lets the default handler finish it. Calling
        # close_page_finish AND returning FALSE finishes the page twice —
        # which trips the page_belongs_to_this_view assertion.
        view.close_page_finish(tab_page, True)
        if self.tab_view.get_n_pages() == 0:
            GLib.idle_add(self.close)
        return True

    def _on_create_window(self, _view: Adw.TabView) -> Adw.TabView:
        new = self.app.spawn_window(present=True)
        return new.tab_view

    def _on_selected_page_changed(self, _obj: GObject.Object, _pspec: GObject.ParamSpec) -> None:
        self._sync_address()
        self._sync_nav_buttons()
        self._sync_progress()
        self._sync_security_icon()
        self._sync_bookmark_button()

    # ------------------------------------------------------------------
    # Per-view signal handlers
    # ------------------------------------------------------------------
    def _is_current(self, view: WebKit.WebView) -> bool:
        return view is self.current_view

    def _on_view_uri_changed(self, view: WebKit.WebView, _pspec: GObject.ParamSpec) -> None:
        if self._is_current(view):
            self._sync_address()
            self._sync_security_icon()
            self._sync_bookmark_button()

    def _on_view_title_changed(self, view: WebKit.WebView, _pspec: GObject.ParamSpec) -> None:
        title = view.get_title() or view.get_uri() or "New Tab"
        page = self.tab_view.get_page(view)
        if page is not None:
            page.set_title(title)
        if self._is_current(view):
            self.set_title(f"{title} — Web")

    def _on_progress_changed(self, view: WebKit.WebView, _pspec: GObject.ParamSpec) -> None:
        if self._is_current(view):
            self._sync_progress()

    def _on_loading_changed(self, view: WebKit.WebView, _pspec: GObject.ParamSpec) -> None:
        if self._is_current(view):
            self._sync_nav_buttons()
            self._sync_progress()

    def _on_load_changed(self, view: WebKit.WebView, event: WebKit.LoadEvent) -> None:
        # WebKit.LoadEvent.FINISHED == 3; on completion, push the page
        # into the shared history store + refresh the security indicator
        # (TLS info is only meaningful post-commit).
        if event == WebKit.LoadEvent.FINISHED:
            uri = view.get_uri() or ""
            title = view.get_title() or uri
            self.store.push_history(uri, title)
        if event in (WebKit.LoadEvent.COMMITTED, WebKit.LoadEvent.FINISHED):
            if self._is_current(view):
                self._sync_security_icon()

    def _on_load_failed(
        self, view: WebKit.WebView, _event: WebKit.LoadEvent, uri: str, error: GLib.Error
    ) -> bool:
        msg = error.message if hasattr(error, "message") else str(error)
        self._toast(f"Failed to load {uri}: {msg}")
        return False

    def _on_load_failed_with_tls_errors(
        self,
        _view: WebKit.WebView,
        uri: str,
        _certificate: Gio.TlsCertificate,
        errors: Gio.TlsCertificateFlags,
    ) -> bool:
        self._toast(f"TLS error loading {uri}: {int(errors)}")
        return False

    def _on_authenticate(
        self, _view: WebKit.WebView, request: WebKit.AuthenticationRequest
    ) -> bool:
        host = request.get_host() if hasattr(request, "get_host") else "server"
        self._toast(f"Authentication requested by {host}")
        return False

    def _on_view_close(self, view: WebKit.WebView) -> None:
        page = self.tab_view.get_page(view)
        if page is not None:
            self.tab_view.close_page(page)

    def _on_context_menu(
        self,
        _view: WebKit.WebView,
        _context_menu: WebKit.ContextMenu,
        hit_test_result: WebKit.HitTestResult,
    ) -> bool:
        if hit_test_result.context_is_link():
            self.address_entry.set_tooltip_text(hit_test_result.get_link_uri())
        elif hit_test_result.context_is_image():
            self.address_entry.set_tooltip_text(hit_test_result.get_image_uri())
        return False

    def _on_context_menu_dismissed(self, *_a: object) -> None:
        self.address_entry.set_tooltip_text(None)

    def _on_view_create(
        self, _view: WebKit.WebView, _navigation_action: WebKit.NavigationAction
    ) -> Gtk.Widget:
        return self.new_tab("about:blank")

    def _on_decide_policy(
        self,
        _view: WebKit.WebView,
        decision: WebKit.PolicyDecision,
        decision_type: WebKit.PolicyDecisionType,
    ) -> bool:
        response_type = _enum_member(
            WebKit.PolicyDecisionType, "RESPONSE", "response", default=2
        )
        new_window_type = _enum_member(
            WebKit.PolicyDecisionType,
            "NEW_WINDOW_ACTION",
            "new_window_action",
            default=1,
        )

        if decision_type == response_type and hasattr(
            decision, "is_mime_type_supported"
        ):
            if not decision.is_mime_type_supported() and hasattr(decision, "download"):
                decision.download()
                return True

        if decision_type == new_window_type:
            uri = self._policy_uri(decision)
            if uri:
                self.new_tab(uri)
                decision.ignore()
                return True

        uri = self._policy_uri(decision)
        if uri and urlparse(uri).scheme in EXTERNAL_SCHEMES:
            try:
                Gio.AppInfo.launch_default_for_uri(uri, None)
                decision.ignore()
                return True
            except Exception as exc:
                self._toast(f"Could not open external URI: {exc}")
        return False

    @staticmethod
    def _policy_uri(decision: Any) -> str:
        action = (
            decision.get_navigation_action()
            if hasattr(decision, "get_navigation_action")
            else None
        )
        request = (
            action.get_request()
            if action is not None and hasattr(action, "get_request")
            else None
        )
        return (
            request.get_uri()
            if request is not None and hasattr(request, "get_uri")
            else ""
        )

    def _on_insecure_content_detected(
        self, _view: WebKit.WebView, event: WebKit.InsecureContentEvent
    ) -> None:
        self._toast(f"Insecure content detected: {event}")

    def _on_mouse_target_changed(
        self, _view: WebKit.WebView, hit_test_result: WebKit.HitTestResult, _modifiers: int
    ) -> None:
        uri = ""
        if hit_test_result.context_is_link():
            uri = hit_test_result.get_link_uri() or ""
        elif hit_test_result.context_is_image():
            uri = hit_test_result.get_image_uri() or ""
        self.address_entry.set_tooltip_text(uri or None)

    def _on_permission_request(
        self, _view: WebKit.WebView, request: WebKit.PermissionRequest
    ) -> bool:
        name = type(request).__name__.replace("PermissionRequest", "")
        self._toast(f"Denied {name or 'permission'} request")
        request.deny()
        return True

    def _on_print_requested(
        self, _view: WebKit.WebView, print_operation: WebKit.PrintOperation
    ) -> bool:
        print_operation.failed.connect(self._on_print_failed)
        print_operation.finished.connect(self._on_print_finished)
        return False

    def _on_query_permission_state(
        self, _view: WebKit.WebView, query: WebKit.PermissionStateQuery
    ) -> bool:
        state = _enum_member(WebKit.PermissionState, "DENIED", "denied", default=1)
        name = query.get_name() if hasattr(query, "get_name") else "permission"
        query.finish(state)
        self._toast(f"Permission state denied for {name}")
        return True

    def _on_ready_to_show(self, view: WebKit.WebView) -> None:
        page = self.tab_view.get_page(view)
        if page is not None:
            self.tab_view.set_selected_page(page)

    def _on_resource_load_started(
        self, _view: WebKit.WebView, resource: WebKit.WebResource, _request: WebKit.URIRequest
    ) -> None:
        resource.failed.connect(self._on_resource_failed)
        resource.failed_with_tls_errors.connect(
            self._on_resource_failed_with_tls_errors
        )
        resource.finished.connect(self._on_resource_finished)
        resource.sent_request.connect(self._on_resource_sent_request)

    def _on_run_as_modal(self, _view: WebKit.WebView) -> None:
        self._toast("Modal web view requested")

    def _on_run_color_chooser(
        self, _view: WebKit.WebView, _request: WebKit.ColorChooserRequest
    ) -> bool:
        return False

    def _on_run_file_chooser(
        self, _view: WebKit.WebView, _request: WebKit.FileChooserRequest
    ) -> bool:
        return False

    def _on_script_dialog(self, _view: WebKit.WebView, dialog: WebKit.ScriptDialog) -> bool:
        message = dialog.get_message() if hasattr(dialog, "get_message") else ""
        if message:
            self._alert("Page Dialog", message)
        return False

    def _on_show_notification(
        self, _view: WebKit.WebView, notification: WebKit.Notification
    ) -> bool:
        title = (
            notification.get_title()
            if hasattr(notification, "get_title")
            else "Notification"
        )
        body = notification.get_body() if hasattr(notification, "get_body") else ""
        self._toast(f"{title}: {body}" if body else title)
        return True

    def _on_show_option_menu(
        self, _view: WebKit.WebView, _menu: WebKit.OptionMenu, _rectangle: object
    ) -> bool:
        return False

    def _on_submit_form(
        self, _view: WebKit.WebView, request: WebKit.FormSubmissionRequest
    ) -> None:
        if hasattr(request, "submit"):
            request.submit()

    def _on_user_message_received(
        self, _view: WebKit.WebView, message: WebKit.UserMessage
    ) -> bool:
        name = message.get_name() if hasattr(message, "get_name") else "message"
        self._toast(f"Page message: {name}")
        return False

    def _on_enter_fullscreen(self, *_a: object) -> bool:
        self.fullscreen()
        return True

    def _on_leave_fullscreen(self, *_a: object) -> bool:
        self.unfullscreen()
        return True

    def _on_web_process_terminated(
        self, _view: WebKit.WebView, reason: WebKit.WebProcessTerminationReason
    ) -> None:
        self._toast(f"Web process terminated: {reason}")

    def _on_view_favicon_changed(self, view: WebKit.WebView, _pspec: GObject.ParamSpec) -> None:
        page = self.tab_view.get_page(view)
        favicon = view.get_favicon() if hasattr(view, "get_favicon") else None
        if page is not None and hasattr(page, "set_icon") and favicon is not None:
            page.set_icon(favicon)

    def _on_view_muted_changed(self, view: WebKit.WebView, _pspec: GObject.ParamSpec) -> None:
        if self._is_current(view):
            self._toast("Muted" if view.get_is_muted() else "Unmuted")

    def _on_view_playing_audio_changed(self, view: WebKit.WebView, _pspec: GObject.ParamSpec) -> None:
        if self._is_current(view) and view.is_playing_audio():  # type: ignore[operator]  # stub mismodels is_playing_audio property, shadowing the real method
            self._toast("Audio playing")

    def _on_view_theme_color_changed(self, view: WebKit.WebView, _pspec: GObject.ParamSpec) -> None:
        if self._is_current(view):
            self._sync_security_icon()

    def _on_back_forward_list_changed(
        self,
        back_forward: WebKit.BackForwardList,
        _item_added: WebKit.BackForwardListItem | None,
        _items_removed: object,
    ) -> None:
        view = self.current_view
        if view is not None and view.get_back_forward_list() is back_forward:
            self._sync_nav_buttons()

    def _on_resource_failed(
        self, resource: WebKit.WebResource, error: GLib.Error
    ) -> None:
        uri = resource.get_uri() if hasattr(resource, "get_uri") else ""
        message = getattr(error, "message", str(error))
        self._toast(f"Resource failed {uri}: {message}")

    def _on_resource_failed_with_tls_errors(
        self,
        resource: WebKit.WebResource,
        _certificate: Gio.TlsCertificate,
        errors: Gio.TlsCertificateFlags,
    ) -> None:
        uri = resource.get_uri() if hasattr(resource, "get_uri") else ""
        self._toast(f"Resource TLS error {uri}: {int(errors)}")

    def _on_resource_finished(self, _resource: WebKit.WebResource) -> None:
        return None

    def _on_resource_sent_request(
        self,
        _resource: WebKit.WebResource,
        _request: WebKit.URIRequest,
        _redirected_response: WebKit.URIResponse | None,
    ) -> None:
        return None

    def _on_print_failed(
        self, _operation: WebKit.PrintOperation, error: GLib.Error
    ) -> None:
        message = getattr(error, "message", str(error))
        self._toast(f"Print failed: {message}")

    def _on_print_finished(self, *_a: object) -> None:
        self._toast("Print finished")

    # ------------------------------------------------------------------
    # UI sync
    # ------------------------------------------------------------------
    def _sync_address(self) -> None:
        view = self.current_view
        if view is None:
            self.address_entry.set_text("")
            return
        uri = view.get_uri() or ""
        if self.address_entry.get_text() != uri:
            self.address_entry.set_text(uri)

    def _sync_nav_buttons(self) -> None:
        view = self.current_view
        if view is None:
            self.back_button.set_sensitive(False)
            self.forward_button.set_sensitive(False)
            return
        self.back_button.set_sensitive(view.can_go_back())
        self.forward_button.set_sensitive(view.can_go_forward())
        if view.is_loading():  # type: ignore[operator]  # stub mismodels is_loading property, shadowing the real method
            self.reload_button.set_icon_name("process-stop-symbolic")
        else:
            self.reload_button.set_icon_name("view-refresh-symbolic")

    def _sync_progress(self) -> None:
        view = self.current_view
        if view is None or not view.is_loading():  # type: ignore[operator]  # stub mismodels is_loading property, shadowing the real method
            self.progress_bar.set_visible(False)
            return
        self.progress_bar.set_visible(True)
        self.progress_bar.set_fraction(view.get_estimated_load_progress())

    def _sync_security_icon(self) -> None:
        """Lock for HTTPS-no-errors, broken-lock for HTTPS-with-errors,
        insecure-channel for HTTP, blank for about:/data:/empty."""
        view = self.current_view
        entry = self.address_entry
        if view is None:
            entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, None)
            return
        uri = view.get_uri() or ""
        scheme = urlparse(uri).scheme
        if not scheme or scheme in ("about", "data", "file"):
            entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, None)
            entry.set_icon_tooltip_text(Gtk.EntryIconPosition.PRIMARY, "")
            return
        if scheme != "https":
            entry.set_icon_from_icon_name(
                Gtk.EntryIconPosition.PRIMARY, "channel-insecure-symbolic"
            )
            entry.set_icon_tooltip_text(
                Gtk.EntryIconPosition.PRIMARY, "Connection is not secure"
            )
            return
        ok, _cert, errors = view.get_tls_info()
        if ok and int(errors) == 0:
            entry.set_icon_from_icon_name(
                Gtk.EntryIconPosition.PRIMARY, "channel-secure-symbolic"
            )
            entry.set_icon_tooltip_text(
                Gtk.EntryIconPosition.PRIMARY, "Connection is secure"
            )
        else:
            entry.set_icon_from_icon_name(
                Gtk.EntryIconPosition.PRIMARY, "channel-insecure-symbolic"
            )
            entry.set_icon_tooltip_text(
                Gtk.EntryIconPosition.PRIMARY, "Certificate problem"
            )

    def _sync_bookmark_button(self) -> None:
        view = self.current_view
        uri = view.get_uri() if view is not None else ""
        bookmarked = bool(uri) and self.store.is_bookmarked(uri)
        action = self.lookup_action("bookmark")
        if isinstance(action, Gio.SimpleAction):
            action.set_state(GLib.Variant.new_boolean(bookmarked))
        icon = "starred-symbolic" if bookmarked else "non-starred-symbolic"
        self.bookmark_button.set_icon_name(icon)

    def _toast(self, text: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast.new(text))

    def _alert(self, heading: str, body: str | None = None) -> None:
        if not hasattr(Adw, "AlertDialog"):
            self._toast(heading if body is None else f"{heading}: {body}")
            return
        dialog = Adw.AlertDialog.new(heading, body)
        dialog.add_response("close", "Close")
        dialog.set_default_response("close")
        dialog.present(self)

    # ------------------------------------------------------------------
    # Menu rebuilders
    # ------------------------------------------------------------------
    @staticmethod
    def _menu_clear(section: Gio.Menu) -> None:
        if hasattr(section, "remove_all"):
            section.remove_all()
        else:
            while section.get_n_items() > 0:
                section.remove(0)

    def _append_uri_items(
        self, section: Gio.Menu, entries: list[dict[str, str]], limit: int
    ) -> None:
        for entry in entries[:limit]:
            uri = entry.get("uri", "")
            title = entry.get("title") or uri
            # Shorten very long titles in the menu.
            label = title if len(title) <= 64 else title[:61] + "…"
            item = Gio.MenuItem.new(label, None)
            item.set_action_and_target_value(
                "win.load-uri", GLib.Variant.new_string(uri)
            )
            section.append_item(item)

    def _rebuild_history_menu(self) -> None:
        for section in (self._history_section, self._history_dropdown_section):
            self._menu_clear(section)
            self._append_uri_items(section, self.store.history, HISTORY_MENU_LIMIT)

    def _rebuild_bookmarks_menu(self) -> None:
        self._menu_clear(self._bookmarks_section)
        self._append_uri_items(
            self._bookmarks_section, self.store.bookmarks, BOOKMARKS_MENU_LIMIT
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_address_activate(self, entry: Gtk.Entry) -> None:
        uri = normalize_address(entry.get_text())
        view = self.current_view or self.new_tab()
        if uri:
            view.load_uri(uri)
        view.grab_focus()

    def _on_new_tab(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        self.new_tab()
        self.address_entry.grab_focus()

    def _on_close_tab(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        page = self.tab_view.get_selected_page()
        if page is not None:
            self.tab_view.close_page(page)

    def _on_back(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        view = self.current_view
        if view is not None and view.can_go_back():
            view.go_back()

    def _on_forward(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        view = self.current_view
        if view is not None and view.can_go_forward():
            view.go_forward()

    def _on_reload(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        view = self.current_view
        if view is None:
            return
        if view.is_loading():  # type: ignore[operator]  # stub mismodels is_loading property, shadowing the real method
            view.stop_loading()
        else:
            view.reload()

    def _on_reload_bypass_cache(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        view = self.current_view
        if view is not None:
            view.reload_bypass_cache()

    def _on_stop(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        view = self.current_view
        if view is not None and view.is_loading():  # type: ignore[operator]  # stub mismodels is_loading property, shadowing the real method
            view.stop_loading()

    def _on_home(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        view = self.current_view or self.new_tab()
        view.load_uri(HOMEPAGE)

    def _on_zoom_in(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        view = self.current_view
        if view is not None:
            view.set_zoom_level(view.get_zoom_level() * 1.1)

    def _on_zoom_out(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        view = self.current_view
        if view is not None:
            view.set_zoom_level(view.get_zoom_level() / 1.1)

    def _on_zoom_reset(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        view = self.current_view
        if view is not None:
            view.set_zoom_level(1.0)

    def _on_focus_address(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        self.address_entry.grab_focus()
        self.address_entry.select_region(0, -1)

    def _on_find(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        self.find_bar.set_visible(True)
        self.find_entry.grab_focus()
        self.find_entry.select_region(0, -1)

    def _on_preferences(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        from examples.web_browser.settings import SettingsWindow

        dialog = SettingsWindow(self.app.state)
        dialog.set_transient_for(self)
        dialog.present()

    def _on_find_changed(self, entry: Gtk.SearchEntry) -> None:
        text = entry.get_text()
        view = self.current_view
        if view is None:
            return
        find = view.get_find_controller()
        if not text:
            find.search_finish()
            self.find_count_label.set_text("")
            return
        find.search(text, self._find_options(), 1000)

    def _on_find_next(self, *_a: object) -> None:
        view = self.current_view
        text = self.find_entry.get_text()
        if view is None or not text:
            return
        find = view.get_find_controller()
        if find.get_search_text():
            find.search_next()
        else:
            find.search(text, self._find_options(), 1000)

    def _on_find_previous(self, *_a: object) -> None:
        view = self.current_view
        text = self.find_entry.get_text()
        if view is None or not text:
            return
        find = view.get_find_controller()
        if find.get_search_text():
            find.search_previous()
        else:
            find.search(text, self._find_options() | WebKit.FindOptions.BACKWARDS, 1000)

    def _on_find_close(self, *_a: object) -> None:
        view = self.current_view
        if view is not None:
            view.get_find_controller().search_finish()
        self.find_count_label.set_text("")
        self.find_bar.set_visible(False)
        if view is not None:
            view.grab_focus()

    def _on_found_text(
        self, _controller: WebKit.FindController, match_count: int
    ) -> None:
        self.find_count_label.set_text(f"{match_count} matches")

    def _on_failed_to_find_text(self, *_a: object) -> None:
        self.find_count_label.set_text("No matches")

    @staticmethod
    def _find_options() -> Any:
        return WebKit.FindOptions.CASE_INSENSITIVE | WebKit.FindOptions.WRAP_AROUND

    def _on_inspect(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        view = self.current_view
        if view is None:
            return
        inspector = view.get_inspector()
        if inspector is not None:
            inspector.show()

    def _on_print(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        view = self.current_view
        if view is None:
            return
        operation = WebKit.PrintOperation.new(view)
        operation.failed.connect(self._on_print_failed)
        operation.finished.connect(self._on_print_finished)
        operation.run_dialog(self)

    def _on_save_page(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        view = self.current_view
        if view is None:
            return
        destination = self.app.page_archive_destination(view.get_title() or "page")
        mode = _enum_member(WebKit.SaveMode, "MHTML", "mhtml", default=0)
        view.save_to_file(  # type: ignore[call-arg]  # stub mismodels WebKit async callback (GAsyncReadyCallback + user_data)
            Gio.File.new_for_path(str(destination)),
            mode,
            None,
            self._on_save_page_done,  # type: ignore[arg-type]  # stub mismodels WebKit async callback signature
            destination,
        )

    def _on_save_page_done(
        self, view: WebKit.WebView, result: Gio.AsyncResult, destination: Path
    ) -> None:
        try:
            view.save_to_file_finish(result)
            self._toast(f"Saved {destination.name}")
        except Exception as exc:
            self._toast(f"Save failed: {exc}")

    def _on_toggle_mute(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        view = self.current_view
        if view is not None:
            view.set_is_muted(not view.get_is_muted())

    def _on_terminate_web_process(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        view = self.current_view
        if view is not None:
            view.terminate_web_process()

    def _on_extensions(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        self._toast(self.app.extensions.summary())

    def _on_reload_extensions(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        self.app.extensions.start(WebKit, Gio)
        self._toast(self.app.extensions.summary())

    def _on_cookies(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        self.app.fetch_cookie_summary(self._on_cookie_summary)

    def _on_cookie_summary(self, ok: bool, message: str | None) -> None:
        self._toast((message or "") if ok else f"Cookie fetch failed: {message}")

    def _on_website_data(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        self.app.fetch_website_data_summary(self._on_website_data_summary)

    def _on_website_data_summary(self, ok: bool, message: str | None) -> None:
        self._toast((message or "") if ok else f"Website data fetch failed: {message}")

    def _on_clear_website_data(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        self.app.clear_website_data(self._on_clear_website_data_done)

    def _on_clear_website_data_done(self, ok: bool, message: str | None) -> None:
        if ok:
            self._toast("Website data cleared")
        else:
            self._toast(f"Failed to clear website data: {message}")

    def _on_next_tab(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        self.tab_view.select_next_page()

    def _on_prev_tab(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        self.tab_view.select_previous_page()

    def _on_load_uri_action(
        self, _action: Gio.SimpleAction, param: GLib.Variant | None
    ) -> None:
        uri = param.get_string() if param is not None else ""
        if not uri:
            return
        view = self.current_view or self.new_tab(uri)
        view.load_uri(uri)

    def _on_bookmark_toggle(self, _action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        view = self.current_view
        if view is None:
            return
        uri = view.get_uri() or ""
        title = view.get_title() or uri
        if not uri:
            return
        now_bookmarked = self.store.toggle_bookmark(uri, title)
        self._toast("Bookmark added" if now_bookmarked else "Bookmark removed")

    def _on_clear_history(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        self.store.clear_history()
        self._toast("History cleared")

    def _on_clear_bookmarks(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        self.store.clear_bookmarks()
        self._toast("Bookmarks cleared")
