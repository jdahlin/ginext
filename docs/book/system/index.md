# Part III — System integration

How your app talks to the OS, the user session, and other apps. This Part is **portal-first**: most integration tasks should go through `xdg-desktop-portal`, which works on every Linux desktop and inside Flatpak sandboxes. Raw DBus and direct system-service calls come second, for cases portals don't yet cover.

## Chapters

1. [DBus with GIO](dbus.md)
2. [Portals (xdg-desktop-portal)](portals.md)
3. [System services overview](services-overview.md)
4. [UPower (battery & power)](upower.md)
5. [NetworkManager](networkmanager.md)
6. [logind (suspend, idle, lock)](logind.md)
7. [GeoClue (location)](geoclue.md)
8. [AccountsService](accounts-service.md)
9. [libsecret (passwords)](libsecret.md)
10. [MPRIS (media)](mpris.md)
11. [Tracker / Localsearch](tracker.md)
12. [GVfs (mounts and trash)](gvfs.md)
13. [GSettings](gsettings.md)
14. [Notifications](notifications.md)
15. [Exposing your own DBus service](dbus-server.md)
