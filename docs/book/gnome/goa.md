# GNOME Online Accounts

> The system service that manages user accounts (Google, Microsoft, Nextcloud, IMAP, WebDAV, …) and hands authenticated credentials to apps. Use this instead of rolling your own OAuth flow.

## What this chapter covers

- What GOA is: the central place users add accounts; the place apps fetch tokens.
- The user flow: Settings → Online Accounts → add → grant. Your app finds the result waiting.
- The DBus API: enumerating accounts, finding ones with capabilities (mail, calendar, files, photos).
- Capabilities and the per-account interfaces: `OAuth2Based`, `Mail`, `Calendar`, `Files`, `Photos`, `Contacts`.
- Requesting a fresh access token: `GetAccessToken`.
- Reacting to account changes (added, removed, re-authenticated).
- Sandbox: GOA is reachable from Flatpak with the right permissions; expected setup.
- When to bypass GOA: services GOA doesn't support; embedded accounts your app owns.

## What you'll be able to do

- Use a Google/Microsoft/Nextcloud account in your app without doing your own OAuth dance.
- Handle the "user removed the account" case gracefully.

## Notes for the writer

- One worked example: pull the user's primary email from the active mail-capable account.
- Be honest about coverage gaps — GOA doesn't have every provider.
