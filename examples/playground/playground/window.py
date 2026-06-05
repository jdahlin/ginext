from pathlib import Path

from ginext import Adw, Gtk

from playground.catalog import BUILTIN_TEMPLATES, TemplateInfo


_UI_DIR = Path(__file__).resolve().parent / "ui"
_WINDOW_UI = (_UI_DIR / "window.ui").read_text()
_TEMPLATE_ROW_UI = (_UI_DIR / "template-row.ui").read_text()


@Gtk.Template(string=_TEMPLATE_ROW_UI)
class TemplateRow(Gtk.ListBoxRow):
    __gtype_name__ = "PygirPlaygroundTemplateRow"

    title_label: Gtk.Label
    summary_label: Gtk.Label
    tech_label: Gtk.Label

    title_label = Gtk.Template.Child()
    summary_label = Gtk.Template.Child()
    tech_label = Gtk.Template.Child()

    def __init__(self, template: TemplateInfo):
        super().__init__()
        self.template = template
        self.title_label.set_label(template.title)
        self.summary_label.set_label(template.summary)
        self.tech_label.set_label(" / ".join(template.technologies))


@Gtk.Template(string=_WINDOW_UI)
class PlaygroundWindow(Adw.ApplicationWindow):
    __gtype_name__ = "PygirPlaygroundWindow"

    gallery_list: Gtk.ListBox
    search_entry: Gtk.SearchEntry
    title_label: Gtk.Label
    summary_label: Gtk.Label
    tech_box: Gtk.Box
    preview_title: Gtk.Label
    preview_subtitle: Gtk.Label
    run_button: Gtk.Button
    reload_button: Gtk.Button
    restore_button: Gtk.Button

    def __init__(self, application):
        super().__init__(application=application)
        self._templates = BUILTIN_TEMPLATES
        self._selected_template = BUILTIN_TEMPLATES[0]
        self._populate_gallery()
        self._select_template(self._selected_template)

    def _populate_gallery(self, query=""):
        needle = query.casefold().strip()
        child = self.gallery_list.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.gallery_list.remove(child)
            child = next_child

        for template in self._templates:
            haystack = " ".join(
                (template.title, template.summary, " ".join(template.technologies))
            ).casefold()
            if needle and needle not in haystack:
                continue
            self.gallery_list.append(TemplateRow(template))

    def _on_search_changed(self, entry):
        self._populate_gallery(entry.get_text())

    def _on_row_activated(self, _list_box, row):
        self._select_template(row.template)

    def _on_run_clicked(self, _button):
        self.preview_subtitle.set_label(
            f"{self._selected_template.title} launch flow will be wired here."
        )

    def _on_reload_clicked(self, _button):
        self.preview_subtitle.set_label(
            f"{self._selected_template.title} live-reload handoff will be wired here."
        )

    def _on_restore_clicked(self, _button):
        self._select_template(self._selected_template)

    def _select_template(self, template: TemplateInfo):
        self._selected_template = template
        self.title_label.set_label(template.title)
        self.summary_label.set_label(template.summary)
        self.preview_title.set_label(template.title)
        self.preview_subtitle.set_label(
            "Blueprint-defined shell now owns the layout. Template preview and "
            "last-frame reload handoff will be wired here."
        )
        self._set_technology_labels(template)

    def _set_technology_labels(self, template: TemplateInfo):
        child = self.tech_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.tech_box.remove(child)
            child = next_child

        for technology in template.technologies:
            label = Gtk.Label(label=technology)
            label.add_css_class("caption")
            label.add_css_class("accent")
            self.tech_box.append(label)
