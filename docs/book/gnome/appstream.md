# AppStream metainfo

> The XML file that turns your app from "a binary" into "a listing in GNOME Software / Flathub." Get it right and Software shows great screenshots and a clear summary; get it wrong and you don't appear at all.

## What this chapter covers

- File name and location: `data/<app-id>.metainfo.xml.in` (in-templated for translations).
- Required elements:
    - `<id>` matching the App ID.
    - `<name>`, `<summary>` (≤ 35 chars, ideally), `<description>` (proper HTML-ish markup).
    - `<metadata_license>` (the metadata's license, often `CC0-1.0`).
    - `<project_license>` (your app's license, SPDX identifier).
    - `<developer id="…">` with `<name>`.
    - `<launchable type="desktop-id">`.
    - `<provides>` (binaries, MIME types).
    - `<categories>`.
- Screenshots: requirements (sizes, ratios), how many, captions, default screenshot.
- `<releases>`: every release with date, version, description. Software displays this as "What's new."
- `<content_rating type="oars-1.1">`: OARS content rating — required for Flathub.
- `<branding>` color and accent metadata (Software uses these).
- `<recommends>` / `<requires>` hardware/display hints (touchscreen, large screen, internet, etc.).
- Validation in CI: `appstreamcli validate --strict`, `flatpak run org.flathub.flatpak-external-data-checker`.
- Common rejection reasons on Flathub and how to avoid them.

## What you'll be able to do

- Author a metainfo file that passes strict validation.
- Provide screenshots and release notes that look right in Software.
- Survive Flathub review without churn.

## Notes for the writer

- This is a finicky chapter; readers will return to it. Make every field a small section with example.
- Maintain a checklist: required → recommended → optional fields.
- Tie to the [Flathub chapter](flathub.md).
