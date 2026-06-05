"""Main window — Adw.ApplicationWindow with address bar, tabbed WebKit views,
history, bookmarks, security indicator, and inspector hookup.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote, urlparse

from goi.repository import Adw, Gio, GLib, Gtk, WebKit


_UI_DIR = Path(__file__).resolve().parent / "resources"
_WINDOW_UI = (_UI_DIR / "window.ui").read_text()
_MENUS_UI = str(_UI_DIR / "menus.ui")

HOMEPAGE = "https://www.gnome.org/"
SEARCH_URL = "https://duckduckgo.com/?q={}"

# Menu cap — surface the most-recent N. The full lists live in Store.
HISTORY_MENU_LIMIT = 25
BOOKMARKS_MENU_LIMIT = 50
EXTERNAL_SCHEMES = {"mailto", "tel", "sms", "irc", "ircs", "magnet"}


def _enum_member(enum, *names, default):
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
class Window(Adw.ApplicationWindow):
    __gtype_name__ = "WebBrowserWindow"

    toast_overlay = Gtk.Template.Child()
    header_bar = Gtk.Template.Child()
    address_entry = Gtk.Template.Child()
    find_bar = Gtk.Template.Child()
    find_entry = Gtk.Template.Child()
    find_count_label = Gtk.Template.Child()
    find_prev_button = Gtk.Template.Child()
    find_next_button = Gtk.Template.Child()
    find_close_button = Gtk.Template.Child()
    back_button = Gtk.Template.Child()
    forward_button = Gtk.Template.Child()
    reload_button = Gtk.Template.Child()
    home_button = Gtk.Template.Child()
    new_tab_button = Gtk.Template.Child()
    bookmark_button = Gtk.Template.Child()
    history_button = Gtk.Template.Child()
    primary_menu_button = Gtk.Template.Child()
    tab_view = Gtk.Template.Child()
    tab_bar = Gtk.Template.Child()
    progress_bar = Gtk.Template.Child()

    def __init__(self, application, store):
        super().__init__(application=application)
        self.app = application
        self.store = store

        builder = Gtk.Builder.new_from_file(_MENUS_UI)
        self.primary_menu_button.set_menu_model(builder.get_object("primary_menu"))
        self.history_button.set_menu_model(builder.get_object("history_menu"))
        self._history_section = builder.get_object("history_section")
        self._history_dropdown_section = builder.get_object("history_dropdown_section")
        self._bookmarks_section = builder.get_object("bookmarks_section")

        # Refresh menus when shared state changes.
        self.store.connect("history-changed", lambda *_: self._rebuild_history_menu())
        self.store.connect(
            "bookmarks-changed",
            lambda *_: (self._rebuild_bookmarks_menu(), self._sync_bookmark_button()),
        )

        self.tab_view.connect("notify::selected-page", self._on_selected_page_changed)
        self.tab_view.connect("close-page", self._on_close_page)
        self.tab_view.connect("create-window", self._on_create_window)

        self.address_entry.connect("activate", self._on_address_activate)
        self.find_entry.connect("search-changed", self._on_find_changed)
        self.find_entry.connect("activate", self._on_find_next)
        self.find_prev_button.connect("clicked", self._on_find_previous)
        self.find_next_button.connect("clicked", self._on_find_next)
        self.find_close_button.connect("clicked", self._on_find_close)

        self._install_actions()
        self._rebuild_history_menu()
        self._rebuild_bookmarks_menu()

    _WIN_ACTIONS = (
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

    def _install_actions(self):
        group = Gio.SimpleActionGroup()
        for name, handler, accels in self._WIN_ACTIONS:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", getattr(self, handler))
            group.add_action(action)
            if accels:
                self.app.set_accels_for_action(f"win.{name}", list(accels))

        # Stateful: bookmark toggle reflects whether the current URI is bookmarked.
        bookmark = Gio.SimpleAction.new_stateful(
            "bookmark", None, GLib.Variant.new_boolean(False)
        )
        bookmark.connect("activate", self._on_bookmark_toggle)
        group.add_action(bookmark)
        self.app.set_accels_for_action("win.bookmark", ["<Primary>d"])

        # Parameterized "load this URI" used by history/bookmark menu items.
        load_uri = Gio.SimpleAction.new("load-uri", GLib.VariantType.new("s"))
        load_uri.connect("activate", self._on_load_uri_action)
        group.add_action(load_uri)

        self.insert_action_group("win", group)

    # ------------------------------------------------------------------
    # Tab lifecycle
    # ------------------------------------------------------------------
    @property
    def current_view(self) -> WebKit.WebView | None:
        page = self.tab_view.get_selected_page()
        return page.get_child() if page is not None else None

    def new_tab(self, uri: str | None = None) -> WebKit.WebView:
        manager = self.app.extensions.create_user_content_manager()
        view = self._new_web_view(manager)
        self.app.apply_settings_to_view(view)

        view.connect("notify::uri", self._on_view_uri_changed)
        view.connect("notify::title", self._on_view_title_changed)
        view.connect("notify::estimated-load-progress", self._on_progress_changed)
        view.connect("notify::is-loading", self._on_loading_changed)
        view.connect("load-changed", self._on_load_changed)
        view.connect("load-failed", self._on_load_failed)
        view.connect(
            "load-failed-with-tls-errors", self._on_load_failed_with_tls_errors
        )
        view.connect("authenticate", self._on_authenticate)
        view.connect("close", self._on_view_close)
        view.connect("context-menu", self._on_context_menu)
        view.connect("context-menu-dismissed", self._on_context_menu_dismissed)
        view.connect("create", self._on_view_create)
        view.connect("decide-policy", self._on_decide_policy)
        view.connect("insecure-content-detected", self._on_insecure_content_detected)
        view.connect("mouse-target-changed", self._on_mouse_target_changed)
        view.connect("permission-request", self._on_permission_request)
        view.connect("print", self._on_print_requested)
        view.connect("query-permission-state", self._on_query_permission_state)
        view.connect("ready-to-show", self._on_ready_to_show)
        view.connect("resource-load-started", self._on_resource_load_started)
        view.connect("run-as-modal", self._on_run_as_modal)
        view.connect("run-color-chooser", self._on_run_color_chooser)
        view.connect("run-file-chooser", self._on_run_file_chooser)
        view.connect("script-dialog", self._on_script_dialog)
        view.connect("show-notification", self._on_show_notification)
        view.connect("show-option-menu", self._on_show_option_menu)
        view.connect("submit-form", self._on_submit_form)
        view.connect("user-message-received", self._on_user_message_received)
        view.connect("enter-fullscreen", self._on_enter_fullscreen)
        view.connect("leave-fullscreen", self._on_leave_fullscreen)
        view.connect("web-process-terminated", self._on_web_process_terminated)
        view.connect("notify::favicon", self._on_view_favicon_changed)
        view.connect("notify::is-muted", self._on_view_muted_changed)
        view.connect("notify::is-playing-audio", self._on_view_playing_audio_changed)
        view.connect("notify::theme-color", self._on_view_theme_color_changed)

        find = view.get_find_controller()
        find.connect("found-text", self._on_found_text)
        find.connect("failed-to-find-text", self._on_failed_to_find_text)

        back_forward = view.get_back_forward_list()
        if back_forward is not None:
            back_forward.connect("changed", self._on_back_forward_list_changed, view)

        tab_page = self.tab_view.append(view)
        tab_page.set_title("New Tab")
        target = uri or HOMEPAGE
        view.load_uri(target)
        self.tab_view.set_selected_page(tab_page)
        return view

    def _new_web_view(self, manager):
        kwargs = {}
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
            return WebKit.WebView.new_with_user_content_manager(manager)
        return WebKit.WebView()

    def _on_close_page(self, view, tab_page):
        # AdwTabView spec: returning TRUE means "I will finish this".
        # Returning FALSE lets the default handler finish it. Calling
        # close_page_finish AND returning FALSE finishes the page twice —
        # which trips the page_belongs_to_this_view assertion.
        view.close_page_finish(tab_page, True)
        if self.tab_view.get_n_pages() == 0:
            GLib.idle_add(self.close)
        return True

    def _on_create_window(self, _view):
        new = self.app.spawn_window(present=True)
        return new.tab_view

    def _on_selected_page_changed(self, *_a):
        self._sync_address()
        self._sync_nav_buttons()
        self._sync_progress()
        self._sync_security_icon()
        self._sync_bookmark_button()

    # ------------------------------------------------------------------
    # Per-view signal handlers
    # ------------------------------------------------------------------
    def _is_current(self, view) -> bool:
        return view is self.current_view

    def _on_view_uri_changed(self, view, _pspec):
        if self._is_current(view):
            self._sync_address()
            self._sync_security_icon()
            self._sync_bookmark_button()

    def _on_view_title_changed(self, view, _pspec):
        title = view.get_title() or view.get_uri() or "New Tab"
        page = self.tab_view.get_page(view)
        if page is not None:
            page.set_title(title)
        if self._is_current(view):
            self.set_title(f"{title} — Web")

    def _on_progress_changed(self, view, _pspec):
        if self._is_current(view):
            self._sync_progress()

    def _on_loading_changed(self, view, _pspec):
        if self._is_current(view):
            self._sync_nav_buttons()
            self._sync_progress()

    def _on_load_changed(self, view, event):
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

    def _on_load_failed(self, view, _event, uri, error):
        msg = error.message if hasattr(error, "message") else str(error)
        self._toast(f"Failed to load {uri}: {msg}")
        return False

    def _on_load_failed_with_tls_errors(self, _view, uri, _certificate, errors):
        self._toast(f"TLS error loading {uri}: {int(errors)}")
        return False

    def _on_authenticate(self, _view, request):
        host = request.get_host() if hasattr(request, "get_host") else "server"
        self._toast(f"Authentication requested by {host}")
        return False

    def _on_view_close(self, view):
        page = self.tab_view.get_page(view)
        if page is not None:
            self.tab_view.close_page(page)

    def _on_context_menu(self, _view, _context_menu, hit_test_result):
        if hit_test_result.context_is_link():
            self.address_entry.set_tooltip_text(hit_test_result.get_link_uri())
        elif hit_test_result.context_is_image():
            self.address_entry.set_tooltip_text(hit_test_result.get_image_uri())
        return False

    def _on_context_menu_dismissed(self, *_a):
        self.address_entry.set_tooltip_text(None)

    def _on_view_create(self, _view, _navigation_action):
        return self.new_tab("about:blank")

    def _on_decide_policy(self, _view, decision, decision_type):
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
    def _policy_uri(decision) -> str:
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

    def _on_insecure_content_detected(self, _view, event):
        self._toast(f"Insecure content detected: {event}")

    def _on_mouse_target_changed(self, _view, hit_test_result, _modifiers):
        uri = ""
        if hit_test_result.context_is_link():
            uri = hit_test_result.get_link_uri() or ""
        elif hit_test_result.context_is_image():
            uri = hit_test_result.get_image_uri() or ""
        self.address_entry.set_tooltip_text(uri or None)

    def _on_permission_request(self, _view, request):
        name = type(request).__name__.replace("PermissionRequest", "")
        self._toast(f"Denied {name or 'permission'} request")
        request.deny()
        return True

    def _on_print_requested(self, _view, print_operation):
        print_operation.connect("failed", self._on_print_failed)
        print_operation.connect("finished", self._on_print_finished)
        return False

    def _on_query_permission_state(self, _view, query):
        state = _enum_member(WebKit.PermissionState, "DENIED", "denied", default=1)
        name = query.get_name() if hasattr(query, "get_name") else "permission"
        query.finish(state)
        self._toast(f"Permission state denied for {name}")
        return True

    def _on_ready_to_show(self, view):
        page = self.tab_view.get_page(view)
        if page is not None:
            self.tab_view.set_selected_page(page)

    def _on_resource_load_started(self, _view, resource, _request):
        resource.connect("failed", self._on_resource_failed)
        resource.connect(
            "failed-with-tls-errors", self._on_resource_failed_with_tls_errors
        )
        resource.connect("finished", self._on_resource_finished)
        resource.connect("sent-request", self._on_resource_sent_request)

    def _on_run_as_modal(self, _view):
        self._toast("Modal web view requested")

    def _on_run_color_chooser(self, _view, _request):
        return False

    def _on_run_file_chooser(self, _view, _request):
        return False

    def _on_script_dialog(self, _view, dialog):
        message = dialog.get_message() if hasattr(dialog, "get_message") else ""
        if message:
            self._alert("Page Dialog", message)
        return False

    def _on_show_notification(self, _view, notification):
        title = (
            notification.get_title()
            if hasattr(notification, "get_title")
            else "Notification"
        )
        body = notification.get_body() if hasattr(notification, "get_body") else ""
        self._toast(f"{title}: {body}" if body else title)
        return True

    def _on_show_option_menu(self, _view, _menu, _rectangle):
        return False

    def _on_submit_form(self, _view, request):
        if hasattr(request, "submit"):
            request.submit()

    def _on_user_message_received(self, _view, message):
        name = message.get_name() if hasattr(message, "get_name") else "message"
        self._toast(f"Page message: {name}")
        return False

    def _on_enter_fullscreen(self, *_a):
        self.fullscreen()
        return True

    def _on_leave_fullscreen(self, *_a):
        self.unfullscreen()
        return True

    def _on_web_process_terminated(self, _view, reason):
        self._toast(f"Web process terminated: {reason}")

    def _on_view_favicon_changed(self, view, _pspec):
        page = self.tab_view.get_page(view)
        favicon = view.get_favicon() if hasattr(view, "get_favicon") else None
        if page is not None and hasattr(page, "set_icon") and favicon is not None:
            page.set_icon(favicon)

    def _on_view_muted_changed(self, view, _pspec):
        if self._is_current(view):
            self._toast("Muted" if view.get_is_muted() else "Unmuted")

    def _on_view_playing_audio_changed(self, view, _pspec):
        if self._is_current(view) and view.is_playing_audio():
            self._toast("Audio playing")

    def _on_view_theme_color_changed(self, view, _pspec):
        if self._is_current(view):
            self._sync_security_icon()

    def _on_back_forward_list_changed(self, _list, _removed, _added, view):
        if self._is_current(view):
            self._sync_nav_buttons()

    def _on_resource_failed(self, resource, error):
        uri = resource.get_uri() if hasattr(resource, "get_uri") else ""
        message = getattr(error, "message", str(error))
        self._toast(f"Resource failed {uri}: {message}")

    def _on_resource_failed_with_tls_errors(self, resource, _certificate, errors):
        uri = resource.get_uri() if hasattr(resource, "get_uri") else ""
        self._toast(f"Resource TLS error {uri}: {int(errors)}")

    def _on_resource_finished(self, _resource):
        return None

    def _on_resource_sent_request(self, _resource, _request, _redirected_response):
        return None

    def _on_print_failed(self, _operation, error):
        message = getattr(error, "message", str(error))
        self._toast(f"Print failed: {message}")

    def _on_print_finished(self, *_a):
        self._toast("Print finished")

    # ------------------------------------------------------------------
    # UI sync
    # ------------------------------------------------------------------
    def _sync_address(self):
        view = self.current_view
        if view is None:
            self.address_entry.set_text("")
            return
        uri = view.get_uri() or ""
        if self.address_entry.get_text() != uri:
            self.address_entry.set_text(uri)

    def _sync_nav_buttons(self):
        view = self.current_view
        if view is None:
            self.back_button.set_sensitive(False)
            self.forward_button.set_sensitive(False)
            return
        self.back_button.set_sensitive(view.can_go_back())
        self.forward_button.set_sensitive(view.can_go_forward())
        if view.is_loading():
            self.reload_button.set_icon_name("process-stop-symbolic")
        else:
            self.reload_button.set_icon_name("view-refresh-symbolic")

    def _sync_progress(self):
        view = self.current_view
        if view is None or not view.is_loading():
            self.progress_bar.set_visible(False)
            return
        self.progress_bar.set_visible(True)
        self.progress_bar.set_fraction(view.get_estimated_load_progress())

    def _sync_security_icon(self):
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

    def _sync_bookmark_button(self):
        view = self.current_view
        uri = view.get_uri() if view is not None else ""
        bookmarked = bool(uri) and self.store.is_bookmarked(uri)
        action = self.lookup_action("bookmark")
        if action is not None:
            action.set_state(GLib.Variant.new_boolean(bookmarked))
        icon = "starred-symbolic" if bookmarked else "non-starred-symbolic"
        self.bookmark_button.set_icon_name(icon)

    def _toast(self, text: str):
        self.toast_overlay.add_toast(Adw.Toast.new(text))

    def _alert(self, heading: str, body: str | None = None):
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
    def _menu_clear(section):
        if hasattr(section, "remove_all"):
            section.remove_all()
        else:
            while section.get_n_items() > 0:
                section.remove(0)

    def _append_uri_items(self, section, entries, limit):
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

    def _rebuild_history_menu(self):
        for section in (self._history_section, self._history_dropdown_section):
            self._menu_clear(section)
            self._append_uri_items(section, self.store.history, HISTORY_MENU_LIMIT)

    def _rebuild_bookmarks_menu(self):
        self._menu_clear(self._bookmarks_section)
        self._append_uri_items(
            self._bookmarks_section, self.store.bookmarks, BOOKMARKS_MENU_LIMIT
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_address_activate(self, entry):
        uri = normalize_address(entry.get_text())
        view = self.current_view or self.new_tab()
        if uri:
            view.load_uri(uri)
        view.grab_focus()

    def _on_new_tab(self, *_a):
        self.new_tab()
        self.address_entry.grab_focus()

    def _on_close_tab(self, *_a):
        page = self.tab_view.get_selected_page()
        if page is not None:
            self.tab_view.close_page(page)

    def _on_back(self, *_a):
        view = self.current_view
        if view is not None and view.can_go_back():
            view.go_back()

    def _on_forward(self, *_a):
        view = self.current_view
        if view is not None and view.can_go_forward():
            view.go_forward()

    def _on_reload(self, *_a):
        view = self.current_view
        if view is None:
            return
        if view.is_loading():
            view.stop_loading()
        else:
            view.reload()

    def _on_reload_bypass_cache(self, *_a):
        view = self.current_view
        if view is not None:
            view.reload_bypass_cache()

    def _on_stop(self, *_a):
        view = self.current_view
        if view is not None and view.is_loading():
            view.stop_loading()

    def _on_home(self, *_a):
        view = self.current_view or self.new_tab()
        view.load_uri(HOMEPAGE)

    def _on_zoom_in(self, *_a):
        view = self.current_view
        if view is not None:
            view.set_zoom_level(view.get_zoom_level() * 1.1)

    def _on_zoom_out(self, *_a):
        view = self.current_view
        if view is not None:
            view.set_zoom_level(view.get_zoom_level() / 1.1)

    def _on_zoom_reset(self, *_a):
        view = self.current_view
        if view is not None:
            view.set_zoom_level(1.0)

    def _on_focus_address(self, *_a):
        self.address_entry.grab_focus()
        self.address_entry.select_region(0, -1)

    def _on_find(self, *_a):
        self.find_bar.set_visible(True)
        self.find_entry.grab_focus()
        self.find_entry.select_region(0, -1)

    def _on_preferences(self, *_a):
        from examples.web_browser.settings import SettingsWindow

        dialog = SettingsWindow(self.app.state)
        dialog.set_transient_for(self)
        dialog.present()

    def _on_find_changed(self, entry):
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

    def _on_find_next(self, *_a):
        view = self.current_view
        text = self.find_entry.get_text()
        if view is None or not text:
            return
        find = view.get_find_controller()
        if find.get_search_text():
            find.search_next()
        else:
            find.search(text, self._find_options(), 1000)

    def _on_find_previous(self, *_a):
        view = self.current_view
        text = self.find_entry.get_text()
        if view is None or not text:
            return
        find = view.get_find_controller()
        if find.get_search_text():
            find.search_previous()
        else:
            find.search(text, self._find_options() | WebKit.FindOptions.BACKWARDS, 1000)

    def _on_find_close(self, *_a):
        view = self.current_view
        if view is not None:
            view.get_find_controller().search_finish()
        self.find_count_label.set_text("")
        self.find_bar.set_visible(False)
        if view is not None:
            view.grab_focus()

    def _on_found_text(self, _controller, match_count):
        self.find_count_label.set_text(f"{match_count} matches")

    def _on_failed_to_find_text(self, *_a):
        self.find_count_label.set_text("No matches")

    @staticmethod
    def _find_options():
        return WebKit.FindOptions.CASE_INSENSITIVE | WebKit.FindOptions.WRAP_AROUND

    def _on_inspect(self, *_a):
        view = self.current_view
        if view is None:
            return
        inspector = view.get_inspector()
        if inspector is not None:
            inspector.show()

    def _on_print(self, *_a):
        view = self.current_view
        if view is None:
            return
        operation = WebKit.PrintOperation.new(view)
        operation.connect("failed", self._on_print_failed)
        operation.connect("finished", self._on_print_finished)
        operation.run_dialog(self)

    def _on_save_page(self, *_a):
        view = self.current_view
        if view is None:
            return
        destination = self.app.page_archive_destination(view.get_title() or "page")
        mode = _enum_member(WebKit.SaveMode, "MHTML", "mhtml", default=0)
        view.save_to_file(
            Gio.File.new_for_path(str(destination)),
            mode,
            None,
            self._on_save_page_done,
            destination,
        )

    def _on_save_page_done(self, view, result, destination):
        try:
            view.save_to_file_finish(result)
            self._toast(f"Saved {destination.name}")
        except Exception as exc:
            self._toast(f"Save failed: {exc}")

    def _on_toggle_mute(self, *_a):
        view = self.current_view
        if view is not None:
            view.set_is_muted(not view.get_is_muted())

    def _on_terminate_web_process(self, *_a):
        view = self.current_view
        if view is not None:
            view.terminate_web_process()

    def _on_extensions(self, *_a):
        self._toast(self.app.extensions.summary())

    def _on_reload_extensions(self, *_a):
        self.app.extensions.start(WebKit, Gio)
        self._toast(self.app.extensions.summary())

    def _on_cookies(self, *_a):
        self.app.fetch_cookie_summary(self._on_cookie_summary)

    def _on_cookie_summary(self, ok: bool, message: str):
        self._toast(message if ok else f"Cookie fetch failed: {message}")

    def _on_website_data(self, *_a):
        self.app.fetch_website_data_summary(self._on_website_data_summary)

    def _on_website_data_summary(self, ok: bool, message: str):
        self._toast(message if ok else f"Website data fetch failed: {message}")

    def _on_clear_website_data(self, *_a):
        self.app.clear_website_data(self._on_clear_website_data_done)

    def _on_clear_website_data_done(self, ok: bool, message: str | None):
        if ok:
            self._toast("Website data cleared")
        else:
            self._toast(f"Failed to clear website data: {message}")

    def _on_next_tab(self, *_a):
        self.tab_view.select_next_page()

    def _on_prev_tab(self, *_a):
        self.tab_view.select_previous_page()

    def _on_load_uri_action(self, _action, param):
        uri = param.get_string() if param is not None else ""
        if not uri:
            return
        view = self.current_view or self.new_tab(uri)
        view.load_uri(uri)

    def _on_bookmark_toggle(self, _action, _param):
        view = self.current_view
        if view is None:
            return
        uri = view.get_uri() or ""
        title = view.get_title() or uri
        if not uri:
            return
        now_bookmarked = self.store.toggle_bookmark(uri, title)
        self._toast("Bookmark added" if now_bookmarked else "Bookmark removed")

    def _on_clear_history(self, *_a):
        self.store.clear_history()
        self._toast("History cleared")

    def _on_clear_bookmarks(self, *_a):
        self.store.clear_bookmarks()
        self._toast("Bookmarks cleared")
