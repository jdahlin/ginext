# PyPI considerations

> Can you `pip install` a GTK app? Mostly no — but the question is more nuanced than that. This chapter is the honest answer.

## What this chapter covers

- Why `pip install` fundamentally doesn't ship GTK:
    - GTK is C; PyPI wheels can't ship the entire GTK + GdkPixbuf + GIR + Adwaita stack.
    - System GTK is required.
- When `pip install` *does* make sense for goi code:
    - A library of utilities on top of goi, consumed by other GTK apps.
    - A command-line tool that happens to use GIO/GLib without a GUI.
    - A developer tool used by people who already have GTK installed.
- What to publish:
    - `pyproject.toml` with `goi` (or equivalent) as a dependency.
    - Source-only distribution; let pip install find goi from PyPI.
    - Avoid binary wheels for the GUI parts.
- Versioning, semver, and changelogs.
- `pipx` for end-user installation of CLI tools.
- The pattern of dual distribution: publish a library to PyPI and a Flatpak of the app on Flathub.

## What you'll be able to do

- Decide honestly whether PyPI is part of your distribution strategy.
- Publish a goi-based library or CLI to PyPI if it is.

## Notes for the writer

- Short, opinionated chapter. The default for GUI apps is "no, use Flatpak."
