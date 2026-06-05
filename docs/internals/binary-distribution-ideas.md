# Binary Distribution Ideas

This note collects early packaging research for the first public `goi`/`ginext`
story. The scope is intentionally narrow: Python apps managed with `uv` and
`pyproject.toml`, with `goi` doing the native packaging work.

## Goals

- Provide one recommended packaging path per platform.
- Keep Flatpak as the primary Linux distribution path.
- Avoid asking users to choose a Windows or macOS packaging backend.
- Let app authors describe their native requirements in `pyproject.toml`.
- Hide native dependency acquisition, runtime layout, and installer mechanics
  behind `goi package`.

## App Corpus Findings

The local app checkout contains many Flatpak-first Python/GI apps, but only a
small subset attempts native Windows or macOS packaging.

- 237 app directories were scanned.
- 173 showed Flatpak packaging evidence.
- Among Flatpak apps, 13 had Windows binary or installer packaging evidence.
- Among Flatpak apps, 11 had macOS binary or app packaging evidence.
- 7 had evidence for both Windows and macOS packaging.

The apps with both Windows and macOS packaging evidence were:

- `gajim`
- `gaphor`
- `lada`
- `quod-libet`
- `ssh-studio`
- `varia`
- `yafi-yet-another-framework-interface`

The strongest PyGObject-oriented cross-platform examples were `gaphor`,
`gajim`, `quod-libet`, `varia`, and `lada`.

The pattern is that projects which ship on Windows and macOS usually avoid
asking users to assemble the native stack themselves. They either bundle a
known runtime, use an application freezer, or maintain custom CI packaging.

The app-specific binary/runtime sources found in the local checkout were:

| App | Windows runtime source | macOS runtime source |
| --- | --- | --- |
| `gajim` | MSYS2/UCRT `pacman` packages staged into an installer, then NSIS and MSIX output. | Homebrew `gtk4`, `libadwaita`, `pygobject3`, GStreamer, and related packages, then PyInstaller/DMG. |
| `gaphor` | Prebuilt `wingtk/gvsbuild` GTK zip plus the PyGObject and pycairo wheels from that zip, then PyInstaller/NSIS. | Homebrew GTK/libadwaita dependencies, then PyInstaller and `dmgbuild`. |
| `quod-libet` | MSYS2 `pacman` packages staged into an installer, then NSIS and a portable self-extracting payload. | A project-owned jhbuild prefix that builds Python, GTK, GStreamer, PyGObject, and dependencies from upstream sources, then gtk-mac-bundler/DMG. |
| `lada` | `gvsbuild` builds the GTK stack and PyGObject/pycairo wheels, or a prebuilt `gvsbuild` dependency archive is downloaded; PyInstaller creates the app payload. | Homebrew GTK/libadwaita/GStreamer. The current `.app` expects the Homebrew GTK/GStreamer runtime rather than fully vendoring it. |
| `varia` | MSYS2/UCRT `pacman` packages for Python/GTK/PyGObject, plus direct downloads of aria2, FFmpeg, Deno, and 7-Zip; PyInstaller plus Inno Setup. | Homebrew GTK/libadwaita/PyGObject, plus direct downloads of aria2, FFmpeg, Deno, and 7-Zip; hand-built `.app` plus DMG. |
| `ssh-studio` | MSYS2/UCRT `pacman`; copies Python, GTK `bin`, `lib`, and `share` trees into the staged app, then Inno Setup. | Homebrew; vendors Python.framework, GTK dylibs, typelibs, PyGObject, and PyCairo into the `.app`. |
| `yafi-yet-another-framework-interface` | Prebuilt `wingtk/gvsbuild` GTK zip plus PyGObject/pycairo wheels, then PyInstaller zip and one-file output. | No actual macOS packaging evidence in the local checkout. |

Takeaway: the reusable Windows paths are MSYS2 runtime staging and
`gvsbuild` runtime staging. The reusable macOS path is Homebrew runtime
staging. Quod Libet's jhbuild approach is the most self-contained macOS model,
but it is much heavier than the path most current apps use.

## Platform Story

Linux:

- Flatpak is the main path.
- The generated Flatpak manifest should build the app from `pyproject.toml`
  using `uv`.
- WebKitGTK is acceptable here because it is already a normal part of the
  Flatpak/GNOME application story.

Windows:

- Support one path only.
- `goi package` should build a frozen application and wrap it in one installer
  format.
- The current preferred shape is PyInstaller output wrapped by Inno Setup.
- Native GTK/GI dependencies should come from a known `goi` runtime artifact
  built from `gvsbuild`.

macOS:

- Support one path only.
- `goi package` should build one `.app` bundle and then a DMG.
- Native GTK/GI dependencies should come from a known `goi` runtime artifact
  staged from Homebrew packages.

## Webview Story

WebKitGTK is probably Linux-only for our purposes. The portable API should not
promise "WebKitGTK everywhere".

A better promise is a small `goi.webview` layer:

- Linux: WebKitGTK inside the Flatpak.
- Windows: WebView2.
- macOS: `WKWebView`.

This lets the announcement demo be a single Python app using a platform-native
webview abstraction. The implementation can start with Linux/WebKitGTK and add
Windows/macOS backends without making WebKitGTK part of the native Windows or
macOS runtime problem.

WebView2 is a separate Windows dependency. It should be handled as a small
optional runtime add-on or installer prerequisite later, not as part of the
first GTK runtime.

## Runtime Builder Choice

Use `gvsbuild` for Windows and Homebrew for macOS.

Windows:

- `gvsbuild` already produces a relocatable GTK tree and Python wheels for
  PyGObject and pycairo.
- Existing apps using it (`gaphor`, `lada`, `yafi`) can install the generated
  wheels into their Python environment and point PyInstaller at the GTK prefix.
- It avoids depending on the end user's MSYS2 installation, while still using a
  maintained Windows GTK build pipeline.
- The artifact should be a narrowed runtime tarball/zip derived from the
  `gvsbuild` output, not the full build directory.

macOS:

- Homebrew is the common source for GTK, libadwaita, PyGObject, PyCairo, and
  GStreamer among the inspected apps.
- The `goi` CI job should stage and vendor the Homebrew runtime into an app
  prefix rather than requiring Homebrew on the user's machine.
- The staged runtime should include dylibs, typelibs, schemas, loaders, icon
  themes, and Python extension modules needed by `gi` and `cairo`.
- The first implementation can build separate `arm64` and `x86_64` artifacts.
  Universal2 can come later if the merge/signing story is worth it.

Cerbero remains worth tracking for GStreamer-specific work, but it is not the
first packaging backend. The inspected Cerbero checkout did not include
libadwaita or WebKitGTK, and the apps we care about are already closer to
`gvsbuild` and Homebrew.

## Artifact Strategy

Do not make `goi` depend on upstream GStreamer MSI/pkg artifacts, a live
Homebrew install on user machines, or a user-managed MSYS2 environment.

Reasons:

- They are broad SDK or installer artifacts, not app-runtime payloads.
- Current CI artifacts are short-lived.
- They include more than most apps need.
- `goi package` wants a relocatable runtime prefix that can be copied into an
  app bundle or installer staging directory.

Instead, build and publish our own narrow runtime artifacts:

Proposed shape:

1. Add CI jobs that build a Windows runtime with `gvsbuild` and macOS runtimes
   from Homebrew.
2. Stage only the runtime files needed by Python/GI apps into a deterministic
   prefix.
3. Emit compressed runtime archives:

   ```sh
   goi-runtime-windows-x86_64-cp313-gtk4.tar.zst
   goi-runtime-macos-arm64-cp313-gtk4.tar.zst
   goi-runtime-macos-x86_64-cp313-gtk4.tar.zst
   ```

4. Publish those archives with stable retention and checksums.
5. Publish a manifest that maps platform, architecture, Python ABI, and runtime
   variant to a URL and checksum.
6. Have `goi package` resolve one artifact, download it, verify it, unpack it
   into a cache, and copy only the needed runtime files into the final app.

Example manifest sketch:

```json
{
  "windows-x86_64-cp313": {
    "runtime": "gtk",
    "builder": "gvsbuild",
    "builder_version": "2026.1.0",
    "url": "https://example.invalid/goi-runtime-windows-x86_64-cp313-gtk4.tar.zst",
    "sha256": "...",
    "python": "3.13.12",
    "gtk": "4.x",
    "libadwaita": "1.x"
  },
  "macos-arm64-cp313": {
    "runtime": "gtk",
    "builder": "homebrew",
    "builder_version": "...",
    "url": "https://example.invalid/goi-runtime-macos-arm64-cp313-gtk4.tar.zst",
    "sha256": "...",
    "python": "3.13.12",
    "gtk": "4.x",
    "libadwaita": "1.x"
  }
}
```

The first runtime should be conservative: GTK4, GLib/Gio/GObject, GObject
Introspection, typelibs, pycairo, and either PyGObject or the `ginext`
equivalent. Full GStreamer media plugins should be optional, not part of the
default GTK runtime unless the app asks for them.

## CI Sketch

Start with GitHub Actions because the reference apps already use it for native
artifacts.

Windows runtime job:

1. Run on `windows-2022`.
2. Install Python and `uv`.
3. Install a pinned `gvsbuild`.
4. Run `gvsbuild build --configuration=release --enable-gi --py-wheel gtk4
   adwaita-icon-theme pygobject libadwaita gettext`.
5. Copy the resulting runtime prefix into `runtime/`.
6. Copy PyGObject and pycairo wheels into `runtime/wheels/`.
7. Prune development files: headers, static libraries, pkg-config files, CMake
   files, GIR XML, docs, tests, and package-manager metadata.
8. Compile or verify schemas, icon cache, and loaders.
9. Run a smoke test using a clean Python environment:

   ```sh
   python -m venv smoke
   smoke/Scripts/python -m pip install runtime/wheels/PyGObject*.whl runtime/wheels/pycairo*.whl
   PATH=runtime/bin:$PATH smoke/Scripts/python -c "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk, Adw"
   ```

10. Archive `runtime/` and upload it.

macOS runtime jobs:

1. Run separate jobs on `macos-15` (`arm64`) and `macos-15-intel` (`x86_64`).
2. Install pinned Homebrew packages: `python@3.13`, `gtk4`, `libadwaita`,
   `pygobject3`, `py3cairo`, `gobject-introspection`, `adwaita-icon-theme`,
   and `gettext`.
3. Stage a runtime prefix from Homebrew:
   - Python.framework or enough Python runtime files for the selected strategy.
   - GTK/libadwaita and dependency dylibs.
   - `gi` and `cairo` Python packages.
   - typelibs from `lib/girepository-1.0`.
   - schemas, icon themes, gdk-pixbuf loaders, and GTK data files.
4. Rewrite install names/rpaths where needed so the staged prefix is
   relocatable inside an `.app`.
5. Ad-hoc sign Mach-O files for the smoke test.
6. Run a smoke test from the staged prefix:

   ```sh
   runtime/bin/python3 -c "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk, Adw"
   ```

7. Archive `runtime/` and upload it.

Release job:

1. Download all runtime artifacts.
2. Generate SHA-256 checksums.
3. Generate `runtimes.json`.
4. Publish archives and manifest to GitHub Releases or another long-retention
   object store.
5. Keep CI artifacts short-lived; treat the release/object-store copies as the
   public inputs used by `goi package`.

The first CI version should prefer clarity over minimal size. Once an app can
successfully package with the runtime, add pruning rules and size checks.

## User-Facing Shape

The user should mostly see `uv` and `pyproject.toml`.

Sketch:

```toml
[project]
dependencies = [
  "goi",
]

[tool.goi]
namespaces = ["Gtk:4.0", "Gio:2.0", "GLib:2.0"]
runtime = "gtk"
webview = true
```

Commands:

```sh
uv run goi run
uv run goi package
```

`goi package` decides the platform backend:

- Linux: Flatpak manifest/build.
- Windows: frozen app plus the supported installer.
- macOS: `.app` plus DMG.

## API Stability

The first release should make the packaging story usable without implying that
every `goi` API is stable. We need room to change the native packaging model
after real applications try it.

Suggested split:

- Stable enough to document: the command names and core project shape.
- Provisional: `tool.goi` keys, runtime names, manifest format, webview API,
  and platform packaging internals.
- Internal: artifact cache layout, exact runtime builder details, PyInstaller
  hook details, installer templates, and copied runtime file lists.

The public contract for the first announcement can be:

```sh
uv run goi run
uv run goi package
```

and:

```toml
[project]
dependencies = ["goi"]

[tool.goi]
namespaces = ["Gtk:4.0", "Gio:2.0", "GLib:2.0"]
```

Everything beyond that should be marked experimental until we have packaged a
few real applications. In particular, `webview = true`, `runtime = "gtk"`, and
runtime artifact manifests should be treated as preview features.

Possible mechanisms:

- Require an explicit preview marker for unstable features:

  ```toml
  [tool.goi]
  preview = ["packaging-v0", "webview-v0"]
  ```

- Version the `tool.goi` schema independently from the Python package:

  ```toml
  [tool.goi]
  schema-version = "0"
  ```

- Emit warnings when a project uses preview configuration.
- Provide `goi migrate` later if the schema changes.
- Avoid promising compatibility for generated installer internals.

This lets early users build real apps while making it clear that the exact
configuration surface is still being shaped by feedback.

## Open Questions

- Which Python ABIs do we publish first: `cp313`, `cp314`, free-threaded, or a
  smaller subset?
- Do we build PyGObject in the runtime initially, or require `ginext` as the
  binding layer from the start?
- Should the first Windows runtime use the `gvsbuild` prebuilt zip, build
  `gvsbuild` from source in our CI, or support both with the same staging
  script?
- Should the first macOS runtime vendor Python.framework, or require app
  packaging to provide Python while the runtime artifact provides GTK/GI only?
- How small can the GTK runtime become without breaking common GI imports,
  icon/theme loading, schemas, and loaders?
- Should media/GStreamer be a separate runtime variant such as
  `runtime = "gtk+gstreamer"`?
- How should signing and notarization fit into the macOS story?
- How should Windows code signing fit into the Inno Setup story?
