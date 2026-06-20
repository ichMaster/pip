"""Orchestration: the one place where body and mind meet.

``Pet`` owns a :class:`~creature.needs.Needs` (the body) and a
:class:`~creature.brain.Brain` (the mind). It is intentionally thin -- it does
not compute drain rates or wording itself; it just routes time and events
between the two halves and applies the mind's mood nudges back onto the body.

**Single-thread-body contract.** The slow part -- asking the mind -- is split
out so it can run off the main thread (v0.4) without ever racing on the body:

* ``snapshot()``  -- copy the body (``Needs`` + ``history``) on the main thread.
* ``think()``     -- ask the mind *about that snapshot*; pure, no body mutation,
                     so it is safe to run on a worker thread.
* ``apply_reply()`` -- fold the reply back onto the live body; **main thread
                     only** (the body has exactly one writer).

``respond()`` is just their synchronous composition, for ``--rule`` and any
caller that wants the old blocking behavior. This is the same invariant the v1.2
daemon reuses, introduced here in miniature.
"""

from __future__ import annotations

import dataclasses
from typing import NamedTuple

from .brain import Brain, Reply
from .needs import Needs

# What each care action does to the body. Kept as data (not buried in code) so
# the rules are easy to read, tweak, and teach.
ACTION_EFFECTS: dict[str, dict[str, float]] = {
    "feed":  {"hunger": +0.45, "mood": +0.05, "energy": +0.05},
    "play":  {"mood": +0.35, "energy": -0.20, "hunger": -0.10},
    "sleep": {"energy": +0.60, "mood": +0.05},
}

# Don't nag more often than this (seconds of real time), scaled by --speed.
SPONTANEOUS_COOLDOWN = 22.0

# Keep this many chat turns in memory; the brain only sees the most recent few.
HISTORY_LIMIT = 8


class Snapshot(NamedTuple):
    """A frozen copy of the body for the mind to read off the main thread."""
    needs: Needs
    history: list[dict[str, str]]


class Pet:
    def __init__(self, name: str, brain: Brain, speed: float = 1.0):
        self.name = name
        self.brain = brain
        self.speed = speed
        self.needs = Needs()
        self.history: list[dict[str, str]] = []  # [{"you": .., name: ..}, ...]
        self.last_spontaneous = 0.0

    def tick(self, dt: float) -> None:
        """Advance the body by `dt` seconds of real elapsed time."""
        self.needs.advance(dt, self.speed)

    def act(self, kind: str) -> None:
        """Apply a care action's numeric effects to the body."""
        for need, delta in ACTION_EFFECTS.get(kind, {}).items():
            setattr(self.needs, need, getattr(self.needs, need) + delta)
        self.needs.clamp()

    def snapshot(self) -> Snapshot:
        """Copy the body so the mind can read it without racing the main thread."""
        return Snapshot(dataclasses.replace(self.needs), list(self.history))

    def think(self, kind: str, user_text: str, snap: Snapshot) -> Reply:
        """Ask the mind for a reply *about a snapshot*. Pure: no body mutation,
        so this is the part that may run on a worker thread."""
        return self.brain.respond(self.name, kind, snap.needs, user_text, snap.history)

    def apply_reply(self, kind: str, user_text: str, reply: Reply) -> str:
        """Fold a reply back onto the live body. MAIN THREAD ONLY (sole writer):
        apply the mood nudge, and for chat append the turn to history."""
        self.needs.mood = min(1.0, max(0.0, self.needs.mood + reply.get("mood", 0.0)))
        say = reply.get("say", "...")
        if kind == "chat":
            self.history.append({"you": user_text, self.name: say})
            self.history[:] = self.history[-HISTORY_LIMIT:]
        return say

    def respond(self, kind: str, user_text: str = "") -> str:
        """Synchronous snapshot -> think -> apply. The old blocking behavior,
        kept for ``--rule`` and any caller that doesn't need the off-thread path."""
        return self.apply_reply(kind, user_text,
                                self.think(kind, user_text, self.snapshot()))

    def spontaneous(self, now: float) -> str | None:
        """An unprompted line if a need is low and the cooldown has elapsed."""
        if now - self.last_spontaneous < SPONTANEOUS_COOLDOWN / max(self.speed, 0.1):
            return None
        line = self.brain.spontaneous(self.name, self.needs)
        if line:
            self.last_spontaneous = now
        return line
