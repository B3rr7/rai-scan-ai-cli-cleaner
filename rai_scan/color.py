"""Dependency-free terminal colors with NO_COLOR and non-TTY support."""

import os
import sys
from typing import Optional, TextIO


RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BRIGHT_RED = "\033[91m"
BRIGHT_GREEN = "\033[92m"
BRIGHT_YELLOW = "\033[93m"
BRIGHT_BLUE = "\033[94m"
BRIGHT_MAGENTA = "\033[95m"
BRIGHT_CYAN = "\033[96m"

# Unicode box-drawing (fallback to ASCII-safe version where needed)
_H = "\u2500"  # ─
_V = "\u2502"  # │
_TL = "\u250c"  # ┌
_TR = "\u2510"  # ┐
_BL = "\u2514"  # └
_BR = "\u2518"  # ┘


def enabled(stream: Optional[TextIO] = None) -> bool:
    output = stream or sys.stdout
    return (
        "NO_COLOR" not in os.environ
        and os.environ.get("TERM", "") != "dumb"
        and hasattr(output, "isatty")
        and output.isatty()
    )


def _sgr(code: str) -> str:
    return code if enabled() else ""


def paint(text: object, *styles: str, stream: Optional[TextIO] = None) -> str:
    value = str(text)
    if not styles or not enabled(stream):
        return value
    return "{}{}{}".format("".join(styles), value, RESET)


def banner(text: str) -> str:
    """Large prominent heading."""
    return paint(text, BOLD, BRIGHT_CYAN)


def heading(text: object) -> str:
    return paint(text, BOLD, CYAN)


def subheading(text: object) -> str:
    return paint(text, BOLD)


def success(text: object) -> str:
    return paint(text, BRIGHT_GREEN)


def warning(text: object) -> str:
    return paint(text, BRIGHT_YELLOW)


def danger(text: object) -> str:
    return paint(text, BOLD, BRIGHT_RED)


def info(text: object) -> str:
    return paint(text, BRIGHT_BLUE)


def muted(text: object) -> str:
    return paint(text, DIM)


def accent(text: object) -> str:
    return paint(text, MAGENTA)


def label(text: object) -> str:
    """Small bright tag label."""
    return paint(text, BOLD, WHITE)


def rule(char: str = "\u2500") -> str:
    """Horizontal rule spanning terminal width."""
    width = 80
    try:
        import shutil
        width = shutil.get_terminal_size(fallback=(80, 20)).columns
    except Exception:
        pass
    return paint(char * width, DIM)


def box(text: str, padding: bool = True) -> str:
    """Wrap text in a unicode box."""
    safe = _H if enabled() else "-"
    tl = _TL if enabled() else "+"
    tr = _TR if enabled() else "+"
    bl = _BL if enabled() else "+"
    br = _BR if enabled() else "+"
    pipe = _V if enabled() else "|"
    lines = text.split("\n")
    max_w = max(len(line) for line in lines) if lines else 0
    gutter = " " if padding else ""
    top = paint(tl + safe * (max_w + 2 * len(gutter)) + tr, DIM)
    bottom = paint(bl + safe * (max_w + 2 * len(gutter)) + br, DIM)
    mid = "\n".join(
        paint(pipe, DIM) + gutter + line.ljust(max_w) + gutter + paint(pipe, DIM)
        for line in lines
    )
    return top + "\n" + mid + "\n" + bottom


def badge(text: str, color: str) -> str:
    """Colored inline tag."""
    return paint(" {} ".format(text), color)


def key_value(key: str, value: str, sep: str = ": ") -> str:
    """Formatted key: value pair."""
    return muted(key) + sep + value


def header_line(left: str, right: str = "", width: int = 80) -> str:
    """Line with left text and right-aligned text."""
    gap = max(0, width - len(left) - len(right))
    return paint(left + " " * gap + right, DIM)
