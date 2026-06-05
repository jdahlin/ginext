# Async Test Targets

Snapshot from the local `apps/` checkout on 2026-05-15.

The scan treated "async usage" broadly:

- Python async: `async def`, `await`, `asyncio`, task helpers.
- GIO/GTK callback async: `*_async(...)` and matching `*_finish(...)`.

Across `apps/`:

- 238 top-level cloned app directories.
- 214 apps show some async signal.
- 142 apps use GIO/GTK-style `*_async` / `*_finish` APIs.
- 677 `*_async(...)` calls.
- 1227 `*_finish(...)` calls.
- 662 `async def` declarations.
- 827 `await` expressions.

## Recommended Targets

### Primary: Gajim

Gajim is the best main async compatibility target.

- Local size: 102.7 KLOC app code, 9.0 KLOC tests, 111.7 KLOC total.
- Async scan: 38 GIO-style async calls and 15 Python async/asyncio signals.
- Uses real GIO async paths including `Gio.File.create_async`,
  `load_contents_async`, clipboard async, and DBus async.
- Mature upstream: the project page reports 23,184 commits, 120 tags, and
  78 releases.
- Active upstream: local clone HEAD is 2026-05-11; Gajim 2.4.6 was released
  2026-04-19.

This is large enough to catch real compatibility issues without relying on
broken or unmaintained app behavior.

### Secondary: Secrets

Secrets is the best smaller modern GNOME target.

- Local size: 9.8 KLOC app code, 0.2 KLOC tests, 10.0 KLOC total.
- Async scan: 72 GIO-style async calls and 32 Python async/asyncio signals.
- Uses GIO async file metadata and app-level async save/check flows.
- Modern GNOME codebase, small enough to debug quickly.

### Other Useful Targets

Cambalache:

- 29.6 KLOC app code, 31.0 KLOC total.
- 39 GIO-style async calls.
- Good GTK-heavy target for file dialogs, stream loading, and GdkPixbuf async.

Apostrophe:

- 7.8 KLOC app code, 8.2 KLOC total.
- 16 GIO-style async calls.
- Smaller modern document app.

Showtime:

- 5.2 KLOC app code.
- 14 GIO-style async calls.
- Maintained GNOME app, but less async-heavy than the others.

## Apps To Avoid As Primary Targets

GNOME Music has a lot of async usage, but it is a weak primary target here:

- Local size: 25.2 KLOC app code.
- Async scan: 164 GIO-style async calls and 353 Python async/asyncio signals.
- It appears less useful as a compatibility benchmark because the app itself
  has been observed as poorly maintained / broken in its latest release.

Quod Libet is mature and large, but less focused on modern GIO/GTK async:

- Local size: 95.8 KLOC app code, 31.7 KLOC tests, 127.5 KLOC total.
- Async scan: 44 GIO-style async calls and 162 Python async/asyncio signals.
- Useful later, but Gajim is a better primary async target for current goals.

## KLOC Summary

Python line counts, excluding obvious build/vendor/cache directories:

| App | App KLOC | Test KLOC | Total KLOC |
| --- | ---: | ---: | ---: |
| Gajim | 102.7 | 9.0 | 111.7 |
| Quod Libet | 95.8 | 31.7 | 127.5 |
| Cambalache | 29.6 | 1.4 | 31.0 |
| GNOME Music | 25.2 | 0.0 | 25.2 |
| Ear Tag | 11.7 | 1.2 | 12.8 |
| Secrets | 9.8 | 0.2 | 10.0 |
| Apostrophe | 7.8 | 0.4 | 8.2 |
| Showtime | 5.2 | 0.0 | 5.2 |

## Recommendation

Use Gajim as the main async compatibility target, with Secrets as the small
modern GNOME sanity check. Add Cambalache when testing GTK-heavy file/stream
async behavior.
