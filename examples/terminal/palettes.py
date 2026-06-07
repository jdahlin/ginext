"""Built-in color palettes for the terminal.

A palette is a (background, foreground, [16 ANSI colors]) triple. Vte
accepts Gdk.RGBA values via set_colors(); we store hex strings here and
build the RGBA list at apply time.
"""

from __future__ import annotations

from ginext import Gdk


_TANGO = [
    "#2e3436",
    "#cc0000",
    "#4e9a06",
    "#c4a000",
    "#3465a4",
    "#75507b",
    "#06989a",
    "#d3d7cf",
    "#555753",
    "#ef2929",
    "#8ae234",
    "#fce94f",
    "#729fcf",
    "#ad7fa8",
    "#34e2e2",
    "#eeeeec",
]

_SOLARIZED_DARK = [
    "#073642",
    "#dc322f",
    "#859900",
    "#b58900",
    "#268bd2",
    "#d33682",
    "#2aa198",
    "#eee8d5",
    "#002b36",
    "#cb4b16",
    "#586e75",
    "#657b83",
    "#839496",
    "#6c71c4",
    "#93a1a1",
    "#fdf6e3",
]

_SOLARIZED_LIGHT = list(_SOLARIZED_DARK)

_LINUX = [
    "#000000",
    "#aa0000",
    "#00aa00",
    "#aa5500",
    "#0000aa",
    "#aa00aa",
    "#00aaaa",
    "#aaaaaa",
    "#555555",
    "#ff5555",
    "#55ff55",
    "#ffff55",
    "#5555ff",
    "#ff55ff",
    "#55ffff",
    "#ffffff",
]

_GRUVBOX_DARK = [
    "#282828",
    "#cc241d",
    "#98971a",
    "#d79921",
    "#458588",
    "#b16286",
    "#689d6a",
    "#a89984",
    "#928374",
    "#fb4934",
    "#b8bb26",
    "#fabd2f",
    "#83a598",
    "#d3869b",
    "#8ec07c",
    "#ebdbb2",
]

_DRACULA = [
    "#21222c",
    "#ff5555",
    "#50fa7b",
    "#f1fa8c",
    "#bd93f9",
    "#ff79c6",
    "#8be9fd",
    "#f8f8f2",
    "#6272a4",
    "#ff6e6e",
    "#69ff94",
    "#ffffa5",
    "#d6acff",
    "#ff92df",
    "#a4ffff",
    "#ffffff",
]

_NORD = [
    "#3b4252",
    "#bf616a",
    "#a3be8c",
    "#ebcb8b",
    "#81a1c1",
    "#b48ead",
    "#88c0d0",
    "#e5e9f0",
    "#4c566a",
    "#bf616a",
    "#a3be8c",
    "#ebcb8b",
    "#81a1c1",
    "#b48ead",
    "#8fbcbb",
    "#eceff4",
]


# (name, background, foreground, ansi[16])
PALETTES: dict[str, tuple[str, str, list[str]]] = {
    "Tango": ("#2e3436", "#eeeeec", _TANGO),
    "Solarized Dark": ("#002b36", "#839496", _SOLARIZED_DARK),
    "Solarized Light": ("#fdf6e3", "#657b83", _SOLARIZED_LIGHT),
    "Linux": ("#000000", "#aaaaaa", _LINUX),
    "Gruvbox Dark": ("#282828", "#ebdbb2", _GRUVBOX_DARK),
    "Dracula": ("#282a36", "#f8f8f2", _DRACULA),
    "Nord": ("#2e3440", "#d8dee9", _NORD),
}

PALETTE_NAMES = list(PALETTES.keys())
DEFAULT_PALETTE = "Tango"


def _rgba(hex_str: str, alpha: float = 1.0) -> Gdk.RGBA:
    rgba = Gdk.RGBA()
    # parse() accepts "#rrggbb"; fall back to black on malformed input.
    if not rgba.parse(hex_str):
        rgba.parse("#000000")
    rgba.alpha = alpha
    return rgba


def resolve(name: str) -> tuple[Gdk.RGBA, Gdk.RGBA, list[Gdk.RGBA]]:
    """Return (background, foreground, ansi[16]) as Gdk.RGBA values."""
    bg_hex, fg_hex, ansi = PALETTES.get(name, PALETTES[DEFAULT_PALETTE])
    bg = _rgba(bg_hex)
    fg = _rgba(fg_hex)
    return bg, fg, [_rgba(c) for c in ansi]
