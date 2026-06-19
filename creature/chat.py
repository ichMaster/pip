"""The real-time chat loop -- where time actually passes.

This is the conductor. Each pass it: advances the body by the real wall-clock
delta, lets the creature speak up on its own if a need is low, then checks for
a line of input *without blocking* (so the body keeps ticking even while you
sit and think). Slash commands are care/info; anything else is conversation.

Input uses ``select`` on stdin, which is Unix-only (macOS/Linux).
"""

from __future__ import annotations

import select
import sys
import time

from .pet import Pet
from .render import BOLD, CYAN, DIM, RESET, face, status_line

HELP = ("  /feed  /play  /sleep   care for me\n"
        "  /status  /help  /quit   info\n"
        "  anything else        just talk to me")

# How long each loop pass waits for input before ticking again. Small enough to
# feel responsive, large enough not to spin the CPU.
POLL_SECONDS = 0.2


def say_line(name: str, text: str) -> None:
    print(f"  {CYAN}{name}{RESET}: {text}")


def _prompt() -> None:
    sys.stdout.write(f"\n  {DIM}you>{RESET} ")
    sys.stdout.flush()


def run(pet: Pet) -> None:
    name = pet.name
    print(f"\n  {BOLD}{face(pet.needs)} {name}{RESET} blinks awake.\n")
    print(HELP + "\n")
    print(status_line(name, pet.needs))
    say_line(name, "hi! i'm so glad you're here.")
    _prompt()

    last = time.time()
    while True:
        now = time.time()
        pet.tick(now - last)   # the body ticks on real elapsed time
        last = now

        spontaneous = pet.spontaneous(now)
        if spontaneous:
            print()
            say_line(name, spontaneous)
            print(status_line(name, pet.needs))
            _prompt()

        # Non-blocking line input: only read if stdin has something ready.
        if select.select([sys.stdin], [], [], POLL_SECONDS)[0]:
            line = sys.stdin.readline()
            if not line:            # EOF (e.g. piped input ran out)
                break
            msg = line.strip()
            if not msg:
                sys.stdout.write(f"  {DIM}you>{RESET} ")
                sys.stdout.flush()
                continue

            if _handle(pet, msg):   # True => user asked to quit
                break
            _prompt()


def _handle(pet: Pet, msg: str) -> bool:
    """Dispatch one line. Returns True if the loop should stop."""
    name = pet.name
    low = msg.lower()

    if low in ("/quit", "/q", "bye"):
        say_line(name, "bye... come back soon.")
        return True
    if low in ("/help", "/h"):
        print(HELP)
    elif low in ("/status", "/s"):
        print(status_line(name, pet.needs))
    elif low in ("/feed", "feed", "/play", "play", "/sleep", "sleep"):
        kind = low.lstrip("/")
        pet.act(kind)
        say_line(name, pet.respond(kind))
        print(status_line(name, pet.needs))
    else:
        say_line(name, pet.respond("chat", msg))
        print(status_line(name, pet.needs))
    return False
