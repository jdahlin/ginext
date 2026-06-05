# Dialogs, toasts, banners

> The Adw way to interrupt and inform: bottom-sheet dialogs on mobile, modals on desktop, toasts for transient feedback, banners for persistent state.

## What this chapter covers

- `Adw.Dialog`: the modern modal — adaptive between bottom sheet (mobile) and centered modal (desktop). The default for new GNOME apps.
- `Adw.AlertDialog`: confirmation/choice prompts. Replaces `Adw.MessageDialog`.
- `Adw.PreferencesDialog`: see the preferences chapter.
- Custom `Adw.Dialog` subclasses with composite templates.
- `Adw.ToastOverlay` and `Adw.Toast`: transient, dismissible, with optional action button. The right choice for "saved," "copied to clipboard," "couldn't connect."
- `Adw.Banner`: persistent in-window banner (e.g., "you're offline," "an update is available, restart").
- When to use which: dialogs for *required* interaction, toasts for *complete* actions, banners for *ongoing* state.
- Async patterns: `dialog.choose(parent, cancellable)` returns awaitable; toasts are fire-and-forget.

## What you'll be able to do

- Pick the right notification surface for a given message.
- Build adaptive dialogs that work on phone and desktop.
- Show toasts and banners idiomatically.

## Notes for the writer

- A decision flowchart ("must they respond?" → dialog; "is this status?" → banner; "did something complete?" → toast) is the most reusable artifact.
- Cross-link to [Dialogs](../building/dialogs.md) for the underlying GTK primitives.
