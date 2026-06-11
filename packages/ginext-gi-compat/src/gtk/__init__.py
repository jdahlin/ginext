"""Stub for the old static gtk binding — raises AttributeError on any access."""


def __getattr__(name: str) -> object:
    raise AttributeError(
        f"gtk is a legacy static binding superseded by gi.repository.Gtk; "
        f"attribute {name!r} is not accessible via this stub"
    )
