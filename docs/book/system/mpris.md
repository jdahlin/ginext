# MPRIS (media)

> The DBus interface that media-playing and media-controlling apps use to talk to each other. If your app plays audio or video, you should expose MPRIS. If your app shows media controls, you should consume it.

## What this chapter covers

- The two MPRIS interfaces: `org.mpris.MediaPlayer2` and `org.mpris.MediaPlayer2.Player` (plus optional `TrackList` and `Playlists`).
- Bus name conventions: `org.mpris.MediaPlayer2.<appname>`.
- Implementing MPRIS as a server:
    - Required properties: `CanQuit`, `CanRaise`, `Identity`, `DesktopEntry`, `SupportedMimeTypes`, `SupportedUriSchemes`.
    - Player properties: `PlaybackStatus`, `LoopStatus`, `Rate`, `Metadata`, `Volume`, `Position`.
    - Methods: `Play`, `Pause`, `Next`, `Previous`, `Seek`, `SetPosition`.
    - Emitting `PropertiesChanged` correctly.
- Implementing MPRIS as a client:
    - Discovering active players (`org.freedesktop.DBus.ListNames`).
    - Subscribing to property changes.
    - Sending control commands.
- Cover art: `mpris:artUrl`, file URIs, cache locations.
- GNOME Shell / KDE Plasma media widget integration.

## What you'll be able to do

- Make your media app appear in the system media controls.
- Build a media-control widget (a remote-style controller) for your app or a panel applet.

## Notes for the writer

- Show one server example and one client example; cross-link.
- Note that mpv, Spotify, browsers, etc. all speak MPRIS — useful for testing.
- This is where the [DBus server chapter](dbus-server.md) really comes into play.
