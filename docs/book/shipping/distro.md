# Distro packages (.deb, .rpm, Arch)

> For most app authors, the right approach is to be friendly to packagers rather than try to be one. This chapter is "what packagers want from your upstream tarball" plus pointers for those who do want to package themselves.

## What this chapter covers

- The upstream contract:
    - A tagged tarball or git tag.
    - `meson install` works with `DESTDIR`.
    - Tests can run from the build directory.
    - All files install to standard `$prefix` locations.
    - License is unambiguous (SPDX in metainfo and `pyproject.toml`).
    - `NEWS` / changelog with release notes.
- Quick tours (overview only — full packaging guides live in distro docs):
    - **Debian / Ubuntu**: `dh_python3`, `debhelper`, `pybuild`. The "pure-Python with assets" pattern.
    - **Fedora / RHEL**: `%pyproject_buildrequires`, `%pyproject_install`, the `python3-gobject-base` dependency.
    - **Arch / pacman**: `PKGBUILD` simplicity, AUR conventions.
- Coordinating with packagers: where to be reachable, what feedback to expect.
- Avoiding packaging hostility: don't bundle system deps in `pip`-installed packages.

## What you'll be able to do

- Produce a release tarball that packagers can work with.
- Self-package for one distro if you must.
- Recognize when "I'll package it myself for every distro" is a trap and Flathub solves the problem better.

## Notes for the writer

- Friendly-upstream tone. Distro packagers do thankless work; don't condescend.
- Cross-link to the [Flatpak](flatpak.md) chapter as the alternative to per-distro packaging.
