"""The BODY: the creature's needs and how they drain over real time.

This module is pure math with no I/O and no LLM. It is one half of the
"two-clock" design (see the package docstring): the body ticks on its own,
deterministically, whether or not anyone is watching. Keeping it free of any
dependency on the mind or the terminal is what makes it easy to test and reason
about.
"""

from __future__ import annotations

from dataclasses import dataclass

# How fast each need drains, as a fraction of the full [0, 1] range per second.
# The keys MUST match the attribute names on `Needs` below -- `advance()` and
# friends iterate over this dict to stay DRY.
DRAIN_PER_SECOND: dict[str, float] = {
    "hunger": 0.008,
    "energy": 0.005,
    "mood": 0.004,
}

# Below this a need is "low"; below this it is "critical". Used for wording and
# for deciding when the creature speaks up on its own.
LOW = 0.6
CRITICAL = 0.3


def clamp(value: float) -> float:
    """Keep a need inside the valid [0, 1] range."""
    return min(1.0, max(0.0, value))


@dataclass
class Needs:
    """The three needs, each in [0, 1] where 1 = good.

    Note `hunger` stores *fullness*: 1.0 means completely full, 0.0 starving.
    That sign convention lets every need share the same "higher is better"
    rule, so rendering and thresholds can treat all three identically.
    """

    hunger: float = 0.8  # fullness
    energy: float = 0.9
    mood: float = 0.7

    def advance(self, dt: float, speed: float = 1.0) -> None:
        """Drain every need by `dt` seconds of real elapsed time.

        `speed` is a global multiplier (the --speed flag) so the same code can
        run a slow, ambient pet or a fast demo.
        """
        for need, rate in DRAIN_PER_SECOND.items():
            drained = getattr(self, need) - rate * dt * speed
            setattr(self, need, max(0.0, drained))

    def clamp(self) -> None:
        """Pull every need back into [0, 1] after a care action nudged it."""
        self.hunger = clamp(self.hunger)
        self.energy = clamp(self.energy)
        self.mood = clamp(self.mood)

    def levels(self) -> dict[str, float]:
        """Numeric snapshot, rounded -- handy for the LLM context and tests."""
        return {need: round(getattr(self, need), 2) for need in DRAIN_PER_SECOND}

    def descriptors(self) -> dict[str, str]:
        """A plain-English word for each need, fed to the LLM as feeling."""

        def band(value: float, low: str, mid: str, high: str) -> str:
            if value < CRITICAL:
                return low
            if value < LOW:
                return mid
            return high

        return {
            "hunger": band(self.hunger, "very hungry", "getting hungry", "well fed"),
            "energy": band(self.energy, "exhausted", "a bit tired", "energetic"),
            "mood": band(self.mood, "sad and lonely", "okay", "happy"),
        }

    def most_urgent(self) -> str:
        """Name of the need with the lowest value -- the one to talk about."""
        return min(DRAIN_PER_SECOND, key=lambda need: getattr(self, need))
