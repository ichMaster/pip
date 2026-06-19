"""pip -- a chat tamagotchi, organized as a small teaching package.

The whole design is one idea: **two clocks.**

    BODY  (needs.py)   ticks on a fast, real-time clock -- pure math, always
                       running, no LLM. The creature gets hungry whether or not
                       you are watching.
    MIND  (brain.py)   is consulted only when there is something to say -- the
                       creature's voice and small mood decisions.

The remaining modules connect those two:

    render.py   draws the face and bars from a body snapshot (pure functions).
    pet.py      the one object that holds a body + a mind and routes between.
    chat.py     the real-time loop: tick, maybe speak, read input, repeat.
    cli.py      parse flags and start the loop.

Run it with ``python pip.py`` (thin launcher) or ``python -m creature``.
"""

from .brain import LLMBrain, RuleBrain, make_brain
from .needs import Needs
from .pet import Pet

__all__ = ["Needs", "Pet", "RuleBrain", "LLMBrain", "make_brain"]
