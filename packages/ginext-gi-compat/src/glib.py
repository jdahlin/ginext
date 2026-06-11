"""Stub for the old static glib binding — raises AttributeError on any access."""


def __getattr__(name: str) -> object:
    raise AttributeError(
        f"glib is a legacy static binding superseded by gi.repository.GLib; "
        f"attribute {name!r} is not accessible via this stub"
    )
