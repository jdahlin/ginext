# libsecret (passwords)

> Storing passwords, tokens, and other secrets via the system keyring (gnome-keyring, KWallet, etc.).

## What this chapter covers

- The Secret Service API and which backends speak it (gnome-keyring, KWallet via kwalletmanager5/6, others).
- libsecret API: schemas, attributes, collections, items.
- The schema-based pattern: define attribute names + types once, store/retrieve by attributes.
- Simple API: `password_store` / `password_lookup` / `password_clear`.
- Collections: default vs login keyring; locking/unlocking.
- Async patterns: never block the main loop for keyring access.
- Sandbox considerations: the Secret Service is reachable through the portal Secret API in Flatpak.

## What you'll be able to do

- Store and retrieve secrets without hand-rolling encryption.
- Use schemas to keep your stored items tidy and discoverable.
- Handle keyring-locked failure modes gracefully.

## Notes for the writer

- One worked example: store an OAuth refresh token keyed by account.
- Be explicit that libsecret is not "encryption" — it's "leave it to the keyring," and the keyring's security is the user's session.
