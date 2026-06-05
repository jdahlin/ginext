"""goi docviewer prototype.

A GTK4 viewer for Markdown files where ```python {goi:run} fences
become editable+runnable example blocks. Each runnable block hosts a
private Casilda compositor; clicking Run spawns Python under that
compositor and the example's window is composited inline.

Run via:

    source tools/docviewer/env.sh
    python tools/docviewer/docviewer.py tools/docviewer/example.md
"""

from __future__ import annotations

import importlib
import os
import re
import signal
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import goi as _gir

_gir.install_as_gi()
_gir.require_versions(
    {
        "Gtk": "4.0",
        "GtkSource": "5",
        "Casilda": "1.0",
    }
)

gi_repository = importlib.import_module("gi.repository")
GLib = gi_repository.GLib
Gtk = gi_repository.Gtk
GtkSource = gi_repository.GtkSource
Casilda = gi_repository.Casilda


PREVIEW_HEIGHT = 520
EDITOR_MIN_HEIGHT = 280

FENCE_RE = re.compile(r"^```(\w+)?(?:\s*\{([^}]*)\})?\s*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
INLINE_CODE_RE = re.compile(r"`([^`]+)`")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


@dataclass
class CodeBlock:
    lang: str
    attrs: str
    src: str

    @property
    def runnable(self) -> bool:
        return self.lang == "python" and "goi:run" in self.attrs


@dataclass
class Heading:
    level: int
    text: str


@dataclass
class Paragraph:
    text: str


def parse_markdown(text: str) -> list:
    blocks: list = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = FENCE_RE.match(line)
        if m:
            lang = m.group(1) or ""
            attrs = m.group(2) or ""
            i += 1
            buf: list[str] = []
            while i < len(lines) and not FENCE_RE.match(lines[i]):
                buf.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            blocks.append(CodeBlock(lang, attrs, "\n".join(buf)))
            continue
        m = HEADING_RE.match(line)
        if m:
            blocks.append(Heading(len(m.group(1)), m.group(2)))
            i += 1
            continue
        if not line.strip():
            i += 1
            continue
        buf = [line]
        i += 1
        while i < len(lines) and lines[i].strip():
            if FENCE_RE.match(lines[i]) or HEADING_RE.match(lines[i]):
                break
            buf.append(lines[i])
            i += 1
        blocks.append(Paragraph(" ".join(s.strip() for s in buf)))
    return blocks


class RunnableExample(Gtk.Box):
    """Editor + Run/Stop + private Casilda preview."""

    def __init__(self, src: str):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add_css_class("goi-example")
        self.set_margin_top(8)
        self.set_margin_bottom(8)
        # GtkTextView child anchors only honor a child's natural size;
        # set hexpand + a generous size request so the example fills
        # the doc width instead of shrinking to its content width.
        self.set_hexpand(True)
        self.set_size_request(820, -1)

        self._child_pid: int | None = None
        self._tmp: Path | None = None

        # Editor
        lang_mgr = GtkSource.LanguageManager.get_default()
        buf = GtkSource.Buffer.new_with_language(lang_mgr.get_language("python"))
        buf.set_text(src)
        scheme_mgr = GtkSource.StyleSchemeManager.get_default()
        scheme = scheme_mgr.get_scheme("Adwaita") or scheme_mgr.get_scheme("classic")
        if scheme:
            buf.set_style_scheme(scheme)

        editor = GtkSource.View.new_with_buffer(buf)
        editor.set_monospace(True)
        editor.set_show_line_numbers(True)
        editor.set_auto_indent(True)
        editor.set_tab_width(4)
        editor.set_insert_spaces_instead_of_tabs(True)
        editor.set_vexpand(False)

        editor_scroll = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            min_content_height=EDITOR_MIN_HEIGHT,
        )
        editor_scroll.set_child(editor)
        editor_scroll.add_css_class("card")
        editor_scroll.set_hexpand(True)
        editor.set_hexpand(True)
        self._buffer = buf

        # Toolbar
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._run_btn = Gtk.Button(
            label="Run", icon_name="media-playback-start-symbolic"
        )
        self._stop_btn = Gtk.Button(
            label="Stop", icon_name="media-playback-stop-symbolic", sensitive=False
        )
        self._status = Gtk.Label(xalign=0.0, hexpand=True)
        self._status.add_css_class("dim-label")
        self._run_btn.connect("clicked", self._on_run)
        self._stop_btn.connect("clicked", self._on_stop)
        bar.append(self._run_btn)
        bar.append(self._stop_btn)
        bar.append(self._status)

        # Preview
        self._compositor = Casilda.Compositor()
        self._compositor.set_size_request(800, PREVIEW_HEIGHT)
        self._compositor.add_css_class("card")

        self.append(editor_scroll)
        self.append(bar)
        self.append(self._compositor)

    def _set_status(self, msg: str) -> None:
        self._status.set_text(msg)

    def _on_run(self, _btn):
        self._kill_child()
        code = self._buffer.get_text(
            self._buffer.get_start_iter(),
            self._buffer.get_end_iter(),
            False,
        )

        # Write to a temp file so tracebacks have a real filename.
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", prefix="goi-example-", delete=False
        ) as tmp:
            tmp.write(code)
            tmp.flush()
            self._tmp = Path(tmp.name)

        argv = [sys.executable, str(self._tmp)]
        try:
            ok, pid = self._compositor.spawn_async(
                None,
                argv,
                None,
                GLib.SpawnFlags.DEFAULT,
            )
        except GLib.Error as e:
            self._set_status(f"spawn failed: {e.message}")
            return
        if not ok:
            self._set_status("spawn failed")
            return
        self._child_pid = pid
        self._run_btn.set_sensitive(False)
        self._stop_btn.set_sensitive(True)
        self._set_status(f"running (pid {pid})")
        GLib.child_watch_add(GLib.PRIORITY_DEFAULT, pid, self._on_child_exit, None)

    def _on_child_exit(self, pid, status, _data):
        try:
            GLib.spawn_close_pid(pid)
        except OSError:
            pass
        if pid != self._child_pid:
            return False
        self._child_pid = None
        self._run_btn.set_sensitive(True)
        self._stop_btn.set_sensitive(False)
        if os.WIFEXITED(status):
            self._set_status(f"exited (code {os.WEXITSTATUS(status)})")
        elif os.WIFSIGNALED(status):
            self._set_status(f"killed (signal {os.WTERMSIG(status)})")
        else:
            self._set_status(f"exited (status {status})")
        if self._tmp is not None:
            try:
                self._tmp.unlink()
            except OSError:
                pass
            self._tmp = None
        return False

    def _on_stop(self, _btn):
        self._kill_child()

    def _kill_child(self):
        if self._child_pid is None:
            return
        try:
            os.kill(self._child_pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


class DocView(Gtk.ScrolledWindow):
    def __init__(self, blocks: list):
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)

        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_cursor_visible(False)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        text_view.set_left_margin(24)
        text_view.set_right_margin(24)
        text_view.set_top_margin(16)
        text_view.set_bottom_margin(16)
        text_view.set_pixels_above_lines(2)
        text_view.set_pixels_below_lines(2)

        buf = text_view.get_buffer()
        self._buf = buf
        self._text_view = text_view

        self._install_tags(buf)
        self._render(blocks)

        self.set_child(text_view)

    def _install_tags(self, buf: Gtk.TextBuffer) -> None:
        buf.create_tag(
            "h1", weight=700, scale=1.8, pixels_above_lines=12, pixels_below_lines=6
        )
        buf.create_tag(
            "h2", weight=700, scale=1.45, pixels_above_lines=10, pixels_below_lines=4
        )
        buf.create_tag(
            "h3", weight=700, scale=1.2, pixels_above_lines=8, pixels_below_lines=2
        )
        buf.create_tag(
            "h4", weight=700, scale=1.05, pixels_above_lines=6, pixels_below_lines=2
        )
        buf.create_tag("para", pixels_below_lines=8)
        buf.create_tag("code", family="monospace", background="#f3f3f3")
        buf.create_tag(
            "codeblock",
            family="monospace",
            background="#f3f3f3",
            left_margin=36,
            paragraph_background="#f7f7f7",
            pixels_above_lines=4,
            pixels_below_lines=8,
        )
        buf.create_tag("bold", weight=700)

    def _render(self, blocks: list) -> None:
        buf = self._buf
        end = buf.get_end_iter
        for block in blocks:
            if isinstance(block, Heading):
                tag = f"h{min(block.level, 4)}"
                buf.insert_with_tags_by_name(end(), block.text + "\n", tag)
            elif isinstance(block, Paragraph):
                self._insert_inline(block.text + "\n", "para")
            elif isinstance(block, CodeBlock):
                if block.runnable:
                    anchor = buf.create_child_anchor(end())
                    widget = RunnableExample(block.src)
                    self._text_view.add_child_at_anchor(widget, anchor)
                    buf.insert(end(), "\n")
                else:
                    buf.insert_with_tags_by_name(end(), block.src + "\n", "codeblock")

    def _insert_inline(self, text: str, base_tag: str) -> None:
        buf = self._buf
        cursor = 0
        for m in INLINE_CODE_RE.finditer(text):
            if m.start() > cursor:
                buf.insert_with_tags_by_name(
                    buf.get_end_iter(), text[cursor : m.start()], base_tag
                )
            buf.insert_with_tags_by_name(
                buf.get_end_iter(), m.group(1), "code", base_tag
            )
            cursor = m.end()
        if cursor < len(text):
            buf.insert_with_tags_by_name(buf.get_end_iter(), text[cursor:], base_tag)


class DocViewerApp(Gtk.Application):
    def __init__(self, doc_path: Path):
        super().__init__(application_id="org.goi.DocViewer")
        self._doc_path = doc_path

    def do_activate(self):
        text = self._doc_path.read_text(encoding="utf-8")
        blocks = parse_markdown(text)
        view = DocView(blocks)

        win = Gtk.ApplicationWindow(
            application=self,
            title=f"goi docs — {self._doc_path.name}",
            default_width=1280,
            default_height=960,
            child=view,
        )
        win.present()


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    app = DocViewerApp(Path(argv[1]).resolve())
    return app.run([])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
