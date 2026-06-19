"""The real-time chat loop -- where time actually passes.

This is the conductor. Each pass it: advances the body by the real wall-clock
delta, lets the creature speak up on its own if a need is low, then checks for
a line of input *without blocking* (so the body keeps ticking even while you
sit and think). Slash commands are care/info; anything else is conversation.

The face + needs bars live in a **framed ``pip`` panel shown before the chat**
(the welcome banner), and are reprinted on demand -- after a care action or
``/status``. The conversation then scrolls normally below it. There is no
cursor-driven in-place footer here: a panel pinned at the top can't update live
while chat scrolls past it (that's the full-frame client in v1.1), so the
status is a snapshot you refresh, which also keeps the output clean and robust.

Input uses ``select`` on stdin, which is Unix-only (macOS/Linux).
"""

from __future__ import annotations

import select
import shutil
import sys
import time

from .pet import Pet
from .render import (BANNER_MIN_WIDTH, CYAN, DIM, RESET, status_panel,
                     welcome_banner)

HELP = ("  /feed  /play  /sleep   care for me\n"
        "  /status  /help  /quit   info\n"
        "  anything else        just talk to me")

# How long each loop pass waits for input before ticking again. Small enough to
# feel responsive, large enough not to spin the CPU.
POLL_SECONDS = 0.2

# Cap the standalone status panel so it stays a tidy card, not a full-width bar.
STATUS_PANEL_MAX_WIDTH = 44


def _term_width() -> int:
    """Current terminal width in columns (falls back sanely when unknown)."""
    return shutil.get_terminal_size().columns


def say_line(name: str, text: str) -> None:
    print(f"  {CYAN}{name}{RESET}: {text}")


def _prompt() -> None:
    sys.stdout.write(f"\n  {DIM}you>{RESET} ")
    sys.stdout.flush()


def _show_status(pet: Pet) -> None:
    """Print the framed status panel (face + bars) inline, indented to match."""
    width = max(18, min(_term_width() - 2, STATUS_PANEL_MAX_WIDTH))
    for line in status_panel(pet.name, pet.needs, width):
        print("  " + line)


def _draw_intro(pet: Pet) -> None:
    """The welcome banner: a framed ``pip`` status panel beside quick-help.

    Wide terminals get the two-column banner; narrow ones get the status panel
    stacked above plain help. Either way the face greets you before the chat.
    """
    print()
    width = _term_width() - 2          # leave room for the 2-space indent
    if width >= BANNER_MIN_WIDTH:
        for line in welcome_banner(pet.name, width, pet.needs):
            print("  " + line)
    else:
        _show_status(pet)
        print(HELP)
    print()
    say_line(pet.name, "hi! i'm so glad you're here.")


def run(pet: Pet) -> None:
    _draw_intro(pet)
    _prompt()

    last = time.time()
    while True:
        now = time.time()
        pet.tick(now - last)   # the body ticks on real elapsed time
        last = now

        spoken = pet.spontaneous(now)
        if spoken:
            print()
            say_line(pet.name, spoken)
            _prompt()

        # Non-blocking line input: only read if stdin has something ready.
        if select.select([sys.stdin], [], [], POLL_SECONDS)[0]:
            raw = sys.stdin.readline()
            if not raw:             # EOF (e.g. piped input ran out)
                break
            msg = raw.strip()
            if not msg:
                _prompt()
                continue
            if _handle(pet, msg):   # True => user asked to quit
                break
            _prompt()


def _handle(pet: Pet, msg: str) -> bool:
    """Dispatch one line. Returns True if the loop should stop.

    Care actions and ``/status`` reprint the status panel so you see the change;
    plain chat just speaks (run ``/status`` to check on pip).
    """
    name = pet.name
    low = msg.lower()

    if low in ("/quit", "/q", "bye"):
        say_line(name, "bye... come back soon.")
        return True
    if low in ("/help", "/h"):
        print(HELP)
    elif low in ("/status", "/s"):
        _show_status(pet)
    elif low in ("/feed", "feed", "/play", "play", "/sleep", "sleep"):
        kind = low.lstrip("/")
        pet.act(kind)
        say_line(name, pet.respond(kind))
        _show_status(pet)
    else:
        say_line(name, pet.respond("chat", msg))
    return False
