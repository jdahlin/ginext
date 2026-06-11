"""Stub for the old static gtk.gdk binding — raises AttributeError on any access."""


def __getattr__(name: str) -> object:
    raise AttributeError(
        f"gtk.gdk is a legacy static binding superseded by gi.repository.Gdk; "
        f"attribute {name!r} is not accessible via this stub"
    )
