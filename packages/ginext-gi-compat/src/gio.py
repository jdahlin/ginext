"""Stub for the old static gio binding — raises AttributeError on any access."""


def __getattr__(name: str) -> object:
    raise AttributeError(
        f"gio is a legacy static binding superseded by gi.repository.Gio; "
        f"attribute {name!r} is not accessible via this stub"
    )
