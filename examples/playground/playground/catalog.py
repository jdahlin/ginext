from dataclasses import dataclass


@dataclass(frozen=True)
class TemplateInfo:
    id: str
    title: str
    summary: str
    technologies: tuple[str, ...]
    optional_dependencies: tuple[str, ...] = ()


BUILTIN_TEMPLATES = (
    TemplateInfo(
        id="web-browser",
        title="Web Browser",
        summary="Navigation, tabs, history, settings, and optional WebKit preview.",
        technologies=("Adw", "Gio.Action", "Gio.Settings", "WebKitGTK"),
        optional_dependencies=("WebKitGTK",),
    ),
    TemplateInfo(
        id="terminal",
        title="Terminal",
        summary="Tabs, PTY lifecycle, command state, search, and Vte integration.",
        technologies=("Adw", "Vte", "Gio.Settings", "Gio.ListModel"),
        optional_dependencies=("Vte",),
    ),
    TemplateInfo(
        id="chatbot",
        title="Chatbot",
        summary="Provider-neutral assistant UI with streaming replies and patch review.",
        technologies=("Gio.ListStore", "GObject", "async IO", "LLM providers"),
    ),
    TemplateInfo(
        id="todo",
        title="Todo",
        summary="Task model, filtering, persistence, settings, and keyboard actions.",
        technologies=(
            "GObject.Property",
            "Gio.ListStore",
            "Gtk.ListView",
            "Gio.Action",
        ),
    ),
    TemplateInfo(
        id="text-editor",
        title="Text Editor",
        summary="Documents, tabs, file IO, syntax highlighting, and dirty-state handling.",
        technologies=("GtkSourceView", "Gio.File", "Gio.Action", "GSettings"),
        optional_dependencies=("GtkSourceView",),
    ),
    TemplateInfo(
        id="video-player",
        title="Video Player",
        summary="GStreamer playback, playlist state, seeking, volume, and file selection.",
        technologies=("GStreamer", "Gtk", "Gio.File", "Gio.ListModel"),
        optional_dependencies=("GStreamer",),
    ),
    TemplateInfo(
        id="media-organiser",
        title="Media Organiser",
        summary="Asset grid, metadata sidebar, async scanning, filtering, and tagging.",
        technologies=("Gio.ListStore", "Gtk.GridView", "Gdk.Texture", "async IO"),
    ),
)
