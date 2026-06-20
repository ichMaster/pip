"""The real-time chat loop -- where time actually passes.

This is the conductor. Each pass it: advances the body by the real wall-clock
delta, lets the creature speak up on its own if a need is low, then checks for
a line of input *without blocking* (so the body keeps ticking even while you
sit and think). Slash commands are care/info; anything else is conversation.

The mind runs **off the main thread** (v0.4): a care/chat turn snapshots the
body and hands the brain call to a background worker; the main loop keeps
ticking the body and polling input while the reply is in flight, and applies
the reply (`pet.apply_reply`, the body's only writer) when it lands. So the
~1 s LLM call no longer freezes the loop. The face + bars are still shown on
demand -- at startup, after a care action, and on `/status`; no cursor-driven
footer (a live pinned status is the v1.1 full-screen client).

Input uses ``select`` on stdin, which is Unix-only (macOS/Linux).
"""

from __future__ import annotations

import collections
import queue
import select
import shutil
import sys
import threading
import time

from .pet import Pet
from .render import (BANNER_MIN_WIDTH, BOLD, CYAN, DIM, RESET, face,
                     status_line, welcome_banner)

HELP = ("  /feed  /play  /sleep   care for me\n"
        "  /status  /help  /quit   info\n"
        "  anything else        just talk to me")

# How long each loop pass waits for input before ticking again. Small enough to
# feel responsive, large enough not to spin the CPU.
POLL_SECONDS = 0.2

STATUS_PANEL_MAX_WIDTH = 44


def _interactive() -> bool:
    """True on a real terminal; piped/redirected output uses the fixed layout."""
    return sys.stdout.isatty()


def _term_width() -> int:
    """Current terminal width in columns (falls back sanely when unknown)."""
    return shutil.get_terminal_size().columns


def _status_width() -> int | None:
    """Width to draw the status at: terminal width on a TTY, else None (fixed)."""
    return _term_width() if _interactive() else None


def say_line(name: str, text: str) -> None:
    print(f"  {CYAN}{name}{RESET}: {text}")


def _prompt() -> None:
    sys.stdout.write(f"\n  {DIM}you>{RESET} ")
    sys.stdout.flush()


def _show_status(pet: Pet) -> None:
    """Print the face + bars once, here and now (no cursor games, never stale)."""
    print(status_line(pet.name, pet.needs, width=_status_width()))


def _draw_intro(pet: Pet) -> None:
    """Welcome banner on a wide terminal, a plain greeting otherwise, then the
    face + bars -- so pip greets you with its status before the chat starts."""
    name = pet.name
    print()
    avail = _term_width() - 2          # leave room for the 2-space indent
    if _interactive() and avail >= BANNER_MIN_WIDTH:
        for line in welcome_banner(name, avail, pet.needs):
            print("  " + line)
        print()
    else:
        print(f"  {BOLD}{face(pet.needs)} {name}{RESET} blinks awake.\n")
        print(HELP + "\n")
    say_line(name, "hi! i'm so glad you're here.")
    _show_status(pet)


def _spawn_worker(pet: Pet, req_q: queue.Queue, res_q: queue.Queue) -> None:
    """A daemon thread that turns brain requests into replies, one at a time.

    It only ever calls ``pet.think`` (pure, reads a snapshot) -- never touches
    the live body -- so the main thread stays the sole writer. Daemon, so it
    never keeps the process alive (Ctrl-C exits at once).
    """
    def worker() -> None:
        while True:
            req = req_q.get()
            if req is None:           # shutdown sentinel
                return
            kind, text, snap = req
            res_q.put((kind, text, pet.think(kind, text, snap)))

    threading.Thread(target=worker, daemon=True).start()


def run(pet: Pet) -> None:
    _draw_intro(pet)
    _prompt()

    req_q: queue.Queue = queue.Queue()
    res_q: queue.Queue = queue.Queue()
    _spawn_worker(pet, req_q, res_q)

    pending: tuple[str, str] | None = None       # (kind, text) in flight
    waiting: collections.deque = collections.deque()  # (kind, text) queued behind it

    def dispatch(kind: str, text: str) -> tuple[str, str]:
        req_q.put((kind, text, pet.snapshot()))  # snapshot on the MAIN thread
        return (kind, text)

    def deliver(kind: str, text: str, reply: dict) -> None:
        print()
        say_line(pet.name, pet.apply_reply(kind, text, reply))  # apply: MAIN thread

    def drain() -> None:                          # finish in-flight work on exit
        nonlocal pending
        while pending is not None:
            kind, text, reply = res_q.get()       # block until the worker answers
            deliver(kind, text, reply)
            pending = dispatch(*waiting.popleft()) if waiting else None

    last = time.time()
    try:
        while True:
            now = time.time()
            pet.tick(now - last)   # the body keeps ticking, even while thinking
            last = now

            spoken = pet.spontaneous(now)
            if spoken:
                print()
                say_line(pet.name, spoken)
                _prompt()

            # Poll the worker: apply + print a finished reply, then dispatch next.
            if pending is not None:
                try:
                    kind, text, reply = res_q.get_nowait()
                except queue.Empty:
                    pass
                else:
                    deliver(kind, text, reply)
                    _prompt()
                    pending = dispatch(*waiting.popleft()) if waiting else None

            # Non-blocking line input: only read if stdin has something ready.
            if select.select([sys.stdin], [], [], POLL_SECONDS)[0]:
                raw = sys.stdin.readline()
                if not raw:             # EOF (piped input ran out): finish + exit
                    drain()
                    break
                msg = raw.strip()
                if not msg:
                    _prompt()
                    continue
                action, payload = _handle(pet, msg)
                if action == "quit":
                    drain()
                    say_line(pet.name, "bye... come back soon.")
                    break
                if action == "brain":
                    if pending is None:
                        pending = dispatch(*payload)
                    else:
                        waiting.append(payload)
                else:                   # handled synchronously (status/help)
                    _prompt()
    finally:
        req_q.put(None)                 # let the worker stop (it's a daemon anyway)


def _handle(pet: Pet, msg: str) -> tuple[str, tuple[str, str] | None]:
    """Decide what one line does. Returns ``(action, payload)``:

    * ``("quit", None)``                -- stop the loop.
    * ``("none", None)``                -- handled here (status/help); run prompts.
    * ``("brain", (kind, text))``       -- needs a reply from the mind (off-thread).

    A care action applies its numeric effect immediately (`pet.act`, main thread)
    and reprints the status; only its *spoken* line goes through the mind.
    """
    low = msg.lower()

    if low in ("/quit", "/q", "bye"):
        return "quit", None
    if low in ("/help", "/h"):
        print(HELP)
        return "none", None
    if low in ("/status", "/s"):
        _show_status(pet)
        return "none", None
    if low in ("/feed", "feed", "/play", "play", "/sleep", "sleep"):
        kind = low.lstrip("/")
        pet.act(kind)               # numeric effect: immediate, main thread
        _show_status(pet)
        return "brain", (kind, "")  # spoken line: off-thread
    return "brain", ("chat", msg)
