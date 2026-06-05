# CI/CD release flows

> Wiring it all together so a `git tag v1.2.3` produces a Flatpak update PR, signed Windows installer, notarized macOS DMG, and PyPI release in one go.

## What this chapter covers

- The release lifecycle this chapter targets:
    1. Open a release PR (changelog, version bump, AppStream `<release>`).
    2. Merge → tag.
    3. CI builds artifacts for all targets.
    4. Each target's "publish" step runs.
    5. A GitHub release collects everything.
- GitHub Actions recipes (the de-facto default):
    - Linux matrix: lint, test, build Flatpak, build AppImage.
    - Windows: MSYS2 build, bundle, sign, package, upload.
    - macOS: build, sign, notarize, staple, build DMG, upload.
    - Cross-platform Python tests.
- Secrets management: signing certs (Windows, macOS), Apple credentials, Flathub deploy tokens, PyPI tokens.
- Reproducible builds:
    - Pin all toolchain versions.
    - Lock Python deps.
    - Cache strategically; don't cache things that should be fresh per release.
- Flathub-specific automation:
    - `flatpak-external-data-checker` for dep updates.
    - Auto-PRs from the upstream repo into `flathub/<app-id>`.
- Snap Store automation:
    - `snapcraft remote-build` for multi-arch.
    - Release channel promotion in CI.
- Release notes: keep one source of truth (CHANGELOG.md or AppStream `<release>`) and propagate.
- Pre-release safety nets:
    - Beta channels (Flathub Beta, Flatpak nightly).
    - "Smoke test on clean machines" stage before promoting to stable.
- Rollback strategy: how to recall a bad release on each store.

## What you'll be able to do

- Set up an end-to-end release pipeline.
- Cut a release that updates all your channels with a single tag push.
- Recover when one of the targets fails partway.

## Notes for the writer

- The capstone chapter of the book. Tie back to every previous Part.
- Include a complete worked GitHub Actions workflow as the centerpiece.
