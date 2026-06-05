from __future__ import annotations

from pathlib import Path

from commander.fs import File

_HOME = str(Path.home())


def display_file(file_: File) -> str:
    text = file_.path
    if text is None:
        text = file_.parse_name or file_.uri or ""
    return abbreviate_home(text)


def abbreviate_home(text: str) -> str:
    if text == _HOME:
        return "~"
    if text.startswith(_HOME + "/"):
        return "~" + text[len(_HOME) :]
    return text


def expand_home(text: str) -> str:
    if text == "~":
        return _HOME
    if text.startswith("~/"):
        return _HOME + text[1:]
    return text
