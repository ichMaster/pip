"""Orchestration: the one place where body and mind meet.

``Pet`` owns a :class:`~creature.needs.Needs` (the body) and a
:class:`~creature.brain.Brain` (the mind). It is intentionally thin -- it does
not compute drain rates or wording itself; it just routes time and events
between the two halves and applies the mind's mood nudges back onto the body.
"""

from __future__ import annotations

from .brain import Brain
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

    def respond(self, kind: str, user_text: str = "") -> str:
        """Ask the mind for a line, apply its mood nudge, return what to say."""
        reply = self.brain.respond(self.name, kind, self.needs, user_text, self.history)
        self.needs.mood = min(1.0, max(0.0, self.needs.mood + reply.get("mood", 0.0)))
        say = reply.get("say", "...")
        if kind == "chat":
            self.history.append({"you": user_text, self.name: say})
            self.history[:] = self.history[-HISTORY_LIMIT:]
        return say

    def spontaneous(self, now: float) -> str | None:
        """An unprompted line if a need is low and the cooldown has elapsed."""
        if now - self.last_spontaneous < SPONTANEOUS_COOLDOWN / max(self.speed, 0.1):
            return None
        line = self.brain.spontaneous(self.name, self.needs)
        if line:
            self.last_spontaneous = now
        return line
