"""Stub for the old static gobject binding — raises AttributeError on any access."""


def __getattr__(name: str) -> object:
    raise AttributeError(
        f"gobject is a legacy static binding superseded by gi.repository.GObject; "
        f"attribute {name!r} is not accessible via this stub"
    )
