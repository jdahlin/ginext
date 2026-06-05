# macOS bundles and notarization

> Producing a `.app` bundle that runs on macOS, signing it, and getting it past Gatekeeper. The notarization step is where most apps stall.

## What this chapter covers

- The `.app` layout: `Contents/Info.plist`, `Contents/MacOS/<binary>`, `Contents/Resources/`, `Contents/Frameworks/`.
- Bundling:
    - The Python interpreter, your modules, goi.
    - GTK / libadwaita and dependency `.dylib`s.
    - GLib schemas, typelibs, GResources, icons, locales.
    - Tooling: `gtk-mac-bundler` (aging), `py2app` (Python-focused), hand-rolled scripts.
- `Info.plist` essentials:
    - `CFBundleIdentifier` matching your App ID.
    - `LSMinimumSystemVersion`.
    - `NSHighResolutionCapable`.
    - `NSAppleEventsUsageDescription` etc. for permission prompts.
    - File-association declarations (`CFBundleDocumentTypes`).
- Code signing:
    - Apple Developer ID certificate.
    - `codesign --deep --options runtime --entitlements ...`.
    - Hardened runtime requirements.
- Notarization:
    - `xcrun notarytool submit ... --wait`.
    - Stapling the ticket (`xcrun stapler staple`).
    - Common rejection reasons (unsigned `.dylib`s, missing hardened runtime).
- Distribution paths:
    - DMG with the `.app` and an `/Applications` symlink.
    - Homebrew formula (`brew install --cask`).
- Auto-updates: Sparkle is the standard.

## What you'll be able to do

- Produce a signed, notarized `.app` that runs on a clean macOS install.
- Survive Apple's notarization rejections.

## Notes for the writer

- This chapter is painful by nature; lead with empathy and concrete recipes.
- Cross-link to [macOS dev](../beyond-gnome/macos.md) for the development-time concerns.
