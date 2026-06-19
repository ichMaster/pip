"""Rendering: turn a `Needs` snapshot into the face and bars you see.

Everything here is a pure function of the body's state -- give it a `Needs`
and it returns strings. No state of its own, no LLM. This is deliberately the
*only* module that knows about ANSI colors and box-drawing, so the rest of the
program can stay about behavior, not presentation.
"""

from __future__ import annotations

from .needs import Needs

# ---- ANSI helpers (degrade gracefully on terminals that ignore them) -------
def _ansi(code: int) -> str:
    return f"\033[{code}m"


RESET, DIM, BOLD = _ansi(0), _ansi(2), _ansi(1)
CYAN, GREEN, YELLOW, RED = _ansi(36), _ansi(32), _ansi(33), _ansi(31)


# ---- cursor control (for redrawing a fixed region in place) ----------------
# render.py is the *sole owner* of ANSI, so the primitives needed to redraw the
# status block in place live here too. They return escape strings (or "") and
# perform no I/O -- chat.py composes them; it never emits raw escapes itself.
CLEAR_LINE = "\r\033[2K"  # carriage return, then erase the whole line


def cursor_up(n: int) -> str:
    """Escape sequence to move the cursor up ``n`` lines (``""`` when n <= 0)."""
    return f"\033[{n}A" if n > 0 else ""


def clear_line() -> str:
    """Return to column 0 and erase the current line."""
    return CLEAR_LINE


CLEAR_BELOW = "\033[J"  # erase from the cursor to the end of the screen


def clear_below() -> str:
    """Erase everything from the cursor down (the rest of the screen)."""
    return CLEAR_BELOW


def hide_cursor() -> str:
    """Hide the cursor (avoids flicker during a redraw)."""
    return "\033[?25l"


def show_cursor() -> str:
    """Show the cursor again; always paired with :func:`hide_cursor` on exit."""
    return "\033[?25h"


# ---- faces -----------------------------------------------------------------
# (eyes, mouth) per state. Single-width glyphs only, so the box stays aligned.
FACE_PARTS: dict[str, tuple[str, str]] = {
    "happy":  ("^   ^", "\\_/"),
    "ok":     ("o   o", "---"),
    "hungry": ("O   O", " o "),
    "tired":  ("-   -", "~~~"),
    "sad":    (";   ;", "..."),
}
STATE_COLOR = {"happy": GREEN, "ok": CYAN, "hungry": YELLOW, "tired": YELLOW, "sad": RED}
STATE_FACE = {"happy": "(^_^)", "ok": "(._.)", "hungry": "(O_O)",
              "tired": "(-_-)", "sad": "(;_;)"}

#: How many lines the status block occupies -- the boxed face (``face_block``)
#: and ``status_line`` are both 4 lines, so an in-place redraw moves the cursor
#: up this many lines. Keep in sync with ``face_block``.
STATUS_HEIGHT = 4


def face_state(n: Needs) -> str:
    """Pick one mood-face from the needs, as a priority cascade.

    Order matters: a critical physical need (tired, hungry) wins over an
    emotional one (sad), and "happy" only shows when everything is comfortable.
    """
    if n.energy < 0.25:
        return "tired"
    if n.hunger < 0.25:
        return "hungry"
    if n.mood < 0.3:
        return "sad"
    if n.mood > 0.75 and n.hunger > 0.5 and n.energy > 0.5:
        return "happy"
    return "ok"


def face(n: Needs) -> str:
    """The compact one-line face, e.g. ``(^_^)``."""
    return STATE_FACE[face_state(n)]


def face_block(n: Needs) -> list[str]:
    """The four-line boxed face."""
    eyes, mouth = FACE_PARTS[face_state(n)]
    return ["╭───────╮",
            "│" + eyes.center(7) + "│",
            "│" + mouth.center(7) + "│",
            "╰───────╯"]


def bar(value: float, width: int = 10) -> str:
    """A colored ``####----`` meter for a single need in [0, 1]."""
    filled = int(round(value * width))
    color = GREEN if value > 0.5 else (YELLOW if value > 0.25 else RED)
    return color + "#" * filled + DIM + "-" * (width - filled) + RESET


def status_line(name: str, n: Needs) -> str:
    """Boxed face on the left, the three needs bars stacked on the right."""
    color = STATE_COLOR[face_state(n)]
    box = face_block(n)
    right = [f"{DIM}{name}{RESET}",
             f"hunger {bar(n.hunger)}",
             f"energy {bar(n.energy)}",
             f"mood   {bar(n.mood)}"]
    return "\n".join(f"  {color}{box[i]}{RESET}   {right[i]}" for i in range(4))
