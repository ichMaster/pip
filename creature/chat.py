"""The real-time chat loop -- where time actually passes.

This is the conductor. Each pass it: advances the body by the real wall-clock
delta, lets the creature speak up on its own if a need is low, then checks for
a line of input *without blocking* (so the body keeps ticking even while you
sit and think). Slash commands are care/info; anything else is conversation.

The status block (face + bars) is a **fixed picture at the bottom**: a footer
that is redrawn in place rather than reprinted after every turn, so the screen
no longer fills with a stack of stale faces. Conversation lines scroll above
it. All the cursor *arithmetic* lives here; the escape sequences themselves
come from ``render`` (the sole owner of ANSI).

Input uses ``select`` on stdin, which is Unix-only (macOS/Linux).
"""

from __future__ import annotations

import select
import shutil
import sys
import time

from .pet import Pet
from .render import (BANNER_MIN_WIDTH, BOLD, CLEAR_LINE, CYAN, DIM, RESET,
                     STATUS_HEIGHT, clear_below, cursor_up, face, hide_cursor,
                     restore_cursor, save_cursor, show_cursor, status_line,
                     welcome_banner)

HELP = ("  /feed  /play  /sleep   care for me\n"
        "  /status  /help  /quit   info\n"
        "  anything else        just talk to me")

# How long each loop pass waits for input before ticking again. Small enough to
# feel responsive, large enough not to spin the CPU.
POLL_SECONDS = 0.2

# When output is piped (not a terminal) we can't redraw in place, so we drop a
# fresh status snapshot into the log at most this often instead.
REPRINT_SECONDS = 30.0

PROMPT = f"  {DIM}you>{RESET} "


def _interactive() -> bool:
    """True on a real terminal; piped/redirected output skips cursor control."""
    return sys.stdout.isatty()


def _term_width() -> int:
    """Current terminal width in columns (falls back sanely when unknown)."""
    return shutil.get_terminal_size().columns


def _say(name: str, text: str) -> str:
    """One creature line, ready to print."""
    return f"  {CYAN}{name}{RESET}: {text}"


def _echo(text: str) -> str:
    """The user's own line, kept in the scrolled-back conversation."""
    return f"  {DIM}you>{RESET} {text}"


def _draw_footer(pet: Pet) -> None:
    """Paint the status block, then park the cursor at the input prompt.

    On a real terminal the prompt dangles (you type right after it); when piped,
    it sits on its own line so the next printed line never collides with it.
    """
    print(status_line(pet.name, pet.needs))
    if _interactive():
        sys.stdout.write(PROMPT)
        sys.stdout.flush()
    else:
        print(PROMPT.rstrip())


def _reframe(pet: Pet, *, after_enter: bool, echo: str | None,
             lines: list[str], footer: bool = True) -> None:
    """Add conversation line(s) without leaving a trail of old status blocks.

    On a terminal: walk the cursor up to the top of the current footer, wipe
    from there down (the old status block, and the line the shell just echoed),
    reprint the conversation, then repaint the footer at the new bottom. When
    not interactive there is nothing to erase -- we simply append.
    """
    if _interactive():
        # The footer is STATUS_HEIGHT status lines + the prompt line. A pressed
        # Enter echoes a newline, dropping the cursor one extra line below it.
        up = STATUS_HEIGHT + (1 if after_enter else 0)
        sys.stdout.write(cursor_up(up) + "\r" + clear_below())
    if echo is not None:
        print(_echo(echo))
    for line in lines:
        print(line)
    if footer:
        _draw_footer(pet)


def _refresh_status(status: str) -> None:
    """Repaint *only* the status block, in place, leaving the prompt untouched.

    Save where the cursor is (somewhere on the prompt line, maybe mid-word),
    step up over the block, rewrite its lines, then jump back -- so the four
    bars/face update live as the body drains without disturbing what the user
    is typing. The cursor is hidden for the brief hop to avoid flicker.
    """
    body = ("\n").join(CLEAR_LINE + line for line in status.split("\n"))
    sys.stdout.write(hide_cursor() + save_cursor()
                     + cursor_up(STATUS_HEIGHT) + body
                     + restore_cursor() + show_cursor())
    sys.stdout.flush()


def _draw_intro(pet: Pet) -> None:
    """A framed welcome banner on a wide terminal; a plain greeting otherwise.

    The banner scrolls into history like any other line -- it is not the
    persistent footer. Indented two spaces to line up with the rest of the UI.
    """
    name = pet.name
    print()
    avail = _term_width() - 2          # leave room for the 2-space indent
    if _interactive() and avail >= BANNER_MIN_WIDTH:
        for line in welcome_banner(name, avail, pet.needs):
            print("  " + line)
        print()
    else:                              # piped or too narrow: plain log
        print(f"  {BOLD}{face(pet.needs)} {name}{RESET} blinks awake.\n")
        print(HELP + "\n")
        print(_say(name, "hi! i'm so glad you're here."))


def run(pet: Pet) -> None:
    name = pet.name
    interactive = _interactive()
    _draw_intro(pet)
    _draw_footer(pet)
    shown = status_line(name, pet.needs)   # what the footer currently shows

    last = time.time()
    next_log = last + REPRINT_SECONDS      # piped mode: occasional snapshot
    try:
        while True:
            now = time.time()
            pet.tick(now - last)   # the body ticks on real elapsed time
            last = now

            spoken = pet.spontaneous(now)
            if spoken:
                _reframe(pet, after_enter=False, echo=None, lines=[_say(name, spoken)])
                shown = status_line(name, pet.needs)
                next_log = now + REPRINT_SECONDS

            # Keep the picture live as the body drains, without spamming output:
            # redraw only when the rendered status actually changed.
            current = status_line(name, pet.needs)
            if current != shown:
                if interactive:
                    _refresh_status(current)
                    shown = current
                elif now >= next_log:      # piped: drop a snapshot into the log
                    print(current)
                    shown = current
                    next_log = now + REPRINT_SECONDS

            # Non-blocking line input: only read if stdin has something ready.
            if select.select([sys.stdin], [], [], POLL_SECONDS)[0]:
                raw = sys.stdin.readline()
                if not raw:             # EOF (e.g. piped input ran out)
                    break
                msg = raw.strip()
                if not msg:             # bare Enter: just settle the footer back
                    _reframe(pet, after_enter=True, echo=None, lines=[])
                    shown = status_line(name, pet.needs)
                    continue

                lines, quit_ = _handle(pet, msg)
                if quit_:
                    _reframe(pet, after_enter=True, echo=msg, lines=lines, footer=False)
                    break
                _reframe(pet, after_enter=True, echo=msg, lines=lines)
                shown = status_line(name, pet.needs)
    finally:
        if interactive:               # never leave the cursor hidden behind us
            sys.stdout.write(show_cursor())
            sys.stdout.flush()


def _handle(pet: Pet, msg: str) -> tuple[list[str], bool]:
    """Decide *what* the creature says to one line. Returns ``(lines, quit?)``.

    Painting is ``run()``'s job -- this only chooses the words (and applies the
    body effects of a care action), so the two clocks stay cleanly separated.
    """
    name = pet.name
    low = msg.lower()

    if low in ("/quit", "/q", "bye"):
        return [_say(name, "bye... come back soon.")], True
    if low in ("/help", "/h"):
        return HELP.split("\n"), False
    if low in ("/status", "/s"):
        return [], False        # the footer already shows the live status
    if low in ("/feed", "feed", "/play", "play", "/sleep", "sleep"):
        kind = low.lstrip("/")
        pet.act(kind)
        return [_say(name, pet.respond(kind))], False
    return [_say(name, pet.respond("chat", msg))], False
