# Part IV — Writing GNOME apps

A "GNOME app" is more than a GTK app with libadwaita. It's an app that follows the GNOME HIG, uses the platform's conventions for naming and metadata, integrates with the shell, is accessible and translatable, and ships through Flathub. This Part covers all of that — libadwaita is one chapter group inside it, not the whole story.

By the end of this Part you'll be able to take a working GTK app and turn it into a GNOME app that could plausibly apply for GNOME Circle.

## Section A — Foundations of the platform

1. [What makes an app a GNOME app](what-makes-a-gnome-app.md)
2. [The GNOME platform](platform.md)
3. [App ID and naming conventions](app-id.md)

## Section B — Scaffolding & tooling

4. [GNOME Builder](builder.md)
5. [Meson layout for GNOME apps](meson-layout.md)
6. [Blueprint](blueprint.md)
7. [Cambalache (visual UI editor)](cambalache.md)

## Section C — libadwaita

8. [AdwApplication and windows](adw-application.md)
9. [Navigation (NavigationView, Split)](adw-navigation.md)
10. [Adaptive UI and breakpoints](adw-adaptive.md)
11. [Dialogs, toasts, banners](adw-dialogs.md)
12. [Preferences and About windows](adw-preferences.md)
13. [Style classes and AdwStyleManager](adw-styling.md)

## Section D — Visual identity

14. [App icons](app-icons.md)
15. [Symbolic icons](symbolic-icons.md)
16. [CSS for GNOME apps](css.md)

## Section E — Behavior & integration

17. [GSettings the GNOME way](gsettings.md)
18. [Notifications done right](notifications.md)
19. [Shell integration](shell-integration.md)
20. [Search providers](search-providers.md)
21. [Background apps and autostart](background.md)
22. [GNOME Online Accounts](goa.md)
23. [Tracker for content apps](tracker.md)
24. [Color management and display](color-and-display.md)

## Section F — Quality

25. [Accessibility](accessibility.md)
26. [Localization](localization.md)
27. [AppStream metainfo](appstream.md)
28. [User docs (Yelp / web)](user-docs.md)

## Section G — Distribution & community

29. [Publishing to Flathub](flathub.md)
30. [GNOME Circle](circle.md)
