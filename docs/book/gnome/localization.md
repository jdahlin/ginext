# Localization

> Translating your app — strings, metadata, settings descriptions — with gettext and the GNOME translation workflow.

## What this chapter covers

- gettext essentials: `_()`, `N_()`, `ngettext()`, translator comments.
- Marking strings translatable in:
    - Python source.
    - `.ui` XML and `.blp` Blueprint files (`translatable="yes"`).
    - `.desktop.in` (Name, GenericName, Comment, Keywords).
    - `.metainfo.xml.in` (Summary, Description, screenshot captions, releases).
    - GSettings schemas (`<summary>`, `<description>`).
- The `po/` directory: `POTFILES.in`, `LINGUAS`, per-language `.po` files.
- Meson `i18n` module: extracting, merging, installing.
- Generating the `.pot` template; merging back into `.po` files.
- Setting up gettext at runtime: `bindtextdomain`, `textdomain` (and the equivalent invocation in goi).
- Plural forms — get them right with `ngettext`.
- Right-to-left languages: GTK handles most of it; what *you* need to remember (icons, layouts, gestures).
- The GNOME Translation Project (formerly Damned Lies): how translators find your app, how to coordinate.
- Per-translator workflow: clear strings, explanatory comments, screenshots when context matters.

## What you'll be able to do

- Make every user-visible string translatable.
- Set up the gettext pipeline from scratch.
- Work with the GNOME translation community.

## Notes for the writer

- Show the end-to-end loop: mark a string, regenerate `.pot`, translate, install, see it in action.
- Cross-link to AppStream (which has translatable fields of its own).
