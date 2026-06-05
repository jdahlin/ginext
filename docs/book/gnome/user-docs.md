# User docs (Yelp / web)

> User-facing help: how to write it, where it lives, and whether to use Yelp/Mallard or just ship a documentation website.

## What this chapter covers

- The two paths:
    - **Yelp + Mallard**: install help pages with your app; F1 / "Help" opens them. Translatable through the same po infrastructure.
    - **Web docs**: a hosted site (mkdocs, Read the Docs, GitHub Pages). Simpler, more shareable, less integrated.
- When to choose which: offline-first apps and accessibility-critical apps lean toward Yelp; broadly-distributed apps lean toward web.
- Mallard primer: pages, topics, links, navigation. The `mallard-rng` schema. Validating with `yelp-check`.
- Wiring help into your app: `Gtk.Application` "help" action, `Gtk.show_uri` with the `help:` URI scheme, fallback to web.
- Localizing help: per-language directory of `.page` files; po-driven workflow.
- A combined approach: ship a short Yelp manual for common tasks + a web docs site for everything else.

## What you'll be able to do

- Pick a docs strategy that matches your app's audience.
- Author Mallard pages if you go that route, or set up an mkdocs site if you don't.
- Translate documentation alongside the app.

## Notes for the writer

- Be honest that Mallard is niche; most new apps just publish web docs.
- The GNOME-app argument for Mallard is "consistent F1 experience" and "translators already know the workflow."
