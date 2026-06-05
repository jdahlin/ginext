# Installation

> Get goi running on Linux, Windows, and macOS, plus the editor setup that makes day-to-day work pleasant.

## What this chapter covers

- System prerequisites by platform:
    - **Linux**: GTK4, libadwaita, GObject Introspection from the distro package manager (apt/dnf/pacman). Per-distro install recipes.
    - **Windows**: MSYS2 + the `mingw-w64-x86_64-gtk4` family; or the bundled-runtime route.
    - **macOS**: Homebrew (`gtk4`, `libadwaita`, `gobject-introspection`); known quirks.
- Installing goi itself (PyPI, from source, from a wheel).
- Verifying the install: `python -c "import goi; from goi.repository import Gtk"`.
- Editor setup:
    - Type stubs and where they live.
    - LSP configuration (pyright, basedpyright, mypy) — how goi's introspection-driven types surface.
    - Auto-import quirks unique to dynamically-loaded namespaces.
- Virtual environments and system GTK: why GTK is *not* `pip install`-able, what that implies.
- Troubleshooting: missing typelibs, mismatched runtimes, `GI_TYPELIB_PATH` and `LD_LIBRARY_PATH`.

## What you'll be able to do

- Install goi on your OS.
- Verify the install with a one-line import check.
- Configure your editor for autocomplete and type checking.
- Diagnose the most common "it can't find GTK" errors.

## Notes for the writer

- Tabbed code blocks per OS so readers don't scroll past three platforms.
- Use the latest stable GTK4 + libadwaita versions; note the minimums.
- Include a "smoke test" snippet readers can paste at the end.
