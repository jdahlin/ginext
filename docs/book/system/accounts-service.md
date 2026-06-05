# AccountsService

> The system service that exposes user information (real name, icon, language, etc.) without your app having to read `/etc/passwd` directly.

## What this chapter covers

- Where it lives: `org.freedesktop.Accounts` on the system bus, with per-user `User` objects.
- Properties of interest: `RealName`, `UserName`, `IconFile`, `Language`, `Session`.
- Reading the current user's avatar (path to file or via the portal `Account.GetUserInformation`).
- The portal alternative for avatar/real name (recommended in sandboxed apps).
- Watching for property changes (e.g., user changes avatar in Settings).

## What you'll be able to do

- Show the user's real name and avatar in your app.
- Pick the right access path depending on sandbox.

## Notes for the writer

- This is a tiny chapter — one page.
- Cross-link to the [Account portal](portals.md).
