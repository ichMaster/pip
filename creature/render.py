"""Rendering: turn a `Needs` snapshot into the face and bars you see.

Everything here is a pure function of the body's state -- give it a `Needs`
and it returns strings. No state of its own, no LLM. This is deliberately the
*only* module that knows about ANSI colors and box-drawing, so the rest of the
program can stay about behavior, not presentation.
"""

from __future__ import annotations

import re
import unicodedata

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


def save_cursor() -> str:
    """Remember the cursor position, so we can wander off and come back."""
    return "\0337"


def restore_cursor() -> str:
    """Jump back to the position saved by :func:`save_cursor`."""
    return "\0338"


# ---- faces -----------------------------------------------------------------
# (eyes, mouth) per state. The look is Claude-adjacent -- a minimal, sparkle
# motif -- and every glyph is single-width (verified by _assert_faces_single_width
# below), so the 7-wide box always stays aligned.
FACE_PARTS: dict[str, tuple[str, str]] = {
    "happy":    ("✦   ✦", "‿‿‿"),
    "content":  ("✶   ✶", " ‿ "),
    "ok":       ("◦   ◦", " - "),
    "hungry":   ("✺   ✺", " o "),
    "tired":    ("-   -", " ~ "),
    "sad":      ("⌢   ⌢", "..."),
    # `thinking` is a transient UI state (a reply is in flight), not derived
    # from needs: face_state never returns it; it is shown only via the explicit
    # `state=` override (wired up live in v0.3's async brain).
    "thinking": ("✻   ✻", " ⋅ "),
}
STATE_COLOR = {"happy": GREEN, "content": GREEN, "ok": CYAN, "hungry": YELLOW,
               "tired": YELLOW, "sad": RED, "thinking": CYAN}
STATE_FACE = {"happy": "(✦‿✦)", "content": "(✶‿✶)", "ok": "(◦‿◦)",
              "hungry": "(✺o✺)", "tired": "(-_-)", "sad": "(⌢_⌢)",
              "thinking": "(✻⋅✻)"}


# ---- width safety ----------------------------------------------------------
# Sparkle glyphs are tempting but some render double-width, which would smear the
# box. East Asian Width is the stdlib proxy: accept narrow/neutral/halfwidth,
# reject wide/full and the CJK-ambiguous ones. (The box frame itself is exempt --
# it is "ambiguous" too but unchanged and already aligns in practice.)
_SAFE_WIDTHS = {"Na", "N", "H"}  # narrow / neutral / halfwidth -> one column


def is_single_width(ch: str) -> bool:
    """True if ``ch`` reliably occupies a single terminal column."""
    return unicodedata.east_asian_width(ch) in _SAFE_WIDTHS


def _assert_faces_single_width() -> None:
    """Fail loudly at import if any face glyph would break the box alignment."""
    glyphs = {ch for eyes, mouth in FACE_PARTS.values() for ch in eyes + mouth}
    glyphs |= {ch for compact in STATE_FACE.values() for ch in compact}
    bad = sorted(c for c in glyphs if c != " " and not is_single_width(c))
    if bad:
        raise AssertionError(
            "face glyphs must be single-width (else the box smears): "
            + ", ".join(f"U+{ord(c):04X} {c!r}" for c in bad))


_assert_faces_single_width()

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
        return "happy"          # euphoric: everything is great
    if n.mood > 0.5 and n.hunger > 0.5 and n.energy > 0.5:
        return "content"        # comfortable, just not over the moon
    return "ok"


def _resolve_state(n: Needs, state: str | None) -> str:
    """The state to draw: an explicit override, else the needs-derived one.

    The override is how a *transient UI* state like ``"thinking"`` (a reply is
    in flight) gets shown -- it isn't reachable from the needs cascade.
    """
    return state if state is not None else face_state(n)


def face(n: Needs, state: str | None = None) -> str:
    """The compact one-line face, e.g. ``(✦‿✦)``."""
    return STATE_FACE[_resolve_state(n, state)]


def face_block(n: Needs, state: str | None = None) -> list[str]:
    """The four-line boxed face (pass ``state`` to force one, e.g. thinking)."""
    eyes, mouth = FACE_PARTS[_resolve_state(n, state)]
    return ["╭───────╮",
            "│" + eyes.center(7) + "│",
            "│" + mouth.center(7) + "│",
            "╰───────╯"]


def bar(value: float, width: int = 10) -> str:
    """A colored ``####----`` meter for a single need in [0, 1]."""
    filled = int(round(value * width))
    color = GREEN if value > 0.5 else (YELLOW if value > 0.25 else RED)
    return color + "#" * filled + DIM + "-" * (width - filled) + RESET


def status_line(name: str, n: Needs, state: str | None = None) -> str:
    """Boxed face on the left, the three needs bars stacked on the right.

    Pass ``state`` to force the face (e.g. ``"thinking"`` while a reply is in
    flight); without it the face follows the body via ``face_state``.
    """
    st = _resolve_state(n, state)
    color = STATE_COLOR[st]
    box = face_block(n, state=st)
    right = [f"{DIM}{name}{RESET}",
             f"hunger {bar(n.hunger)}",
             f"energy {bar(n.energy)}",
             f"mood   {bar(n.mood)}"]
    return "\n".join(f"  {color}{box[i]}{RESET}   {right[i]}" for i in range(4))


# ---- framing (boxes & columns) ---------------------------------------------
# Pure, width-parameterised helpers for the framed UI (welcome banner, panels).
# They take an explicit ``width`` and return strings -- there is no terminal
# measurement here; chat.py measures (``shutil.get_terminal_size``) and feeds
# the width in, the same way it owns the cursor arithmetic for the footer.
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b[78]")


def _visible_len(s: str) -> int:
    """Length of ``s`` ignoring ANSI escapes -- its on-screen column count."""
    return len(_ANSI_RE.sub("", s))


def _fit(text: str, width: int) -> str:
    """Pad or truncate plain ``text`` to exactly ``width`` columns."""
    if width <= 0:
        return ""
    vis = _visible_len(text)
    if vis < width:
        return text + " " * (width - vis)
    if vis > width:
        return text[:width]      # box content is plain -> safe to slice
    return text


def _title_border(title: str, width: int) -> str:
    """Top border with a title tucked in: ``╭─ title ───╮`` of exact width."""
    maxt = width - 6             # room for "╭─ ", a space, >=1 "─", and "╮"
    if maxt < 1:
        return "╭" + "─" * (width - 2) + "╮"
    t = title[:maxt]
    fill = width - 5 - len(t)
    return "╭─ " + t + " " + "─" * fill + "╮"


def box(lines: list[str], width: int, *, title: str | None = None,
        color: str | None = None) -> list[str]:
    """Wrap ``lines`` in a bordered box exactly ``width`` columns wide.

    Content is padded/truncated to fit (the frame never smears). ``title`` rides
    in the top border; ``color`` wraps the whole frame. Pure -- returns strings.
    """
    width = max(width, 4)
    inner = width - 4           # one space of padding inside each "│" border
    top = _title_border(title, width) if title else "╭" + "─" * (width - 2) + "╮"
    body = ["│ " + _fit(line, inner) + " │" for line in lines]
    bottom = "╰" + "─" * (width - 2) + "╯"
    out = [top, *body, bottom]
    if color:
        out = [f"{color}{line}{RESET}" for line in out]
    return out


def columns(blocks: list[list[str]], *, gap: int = 1) -> list[str]:
    """Place equal-width boxed ``blocks`` side by side, padded to equal height."""
    blocks = [b for b in blocks if b]
    if not blocks:
        return []
    height = max(len(b) for b in blocks)
    widths = [_visible_len(b[0]) for b in blocks]
    sep = " " * gap
    rows = []
    for i in range(height):
        cells = [(b[i] if i < len(b) else " " * w) for b, w in zip(blocks, widths)]
        rows.append(sep.join(cells))
    return rows
