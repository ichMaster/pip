"""The MIND: the creature's voice and small decisions.

This is the other half of the "two-clock" design. The body (``needs.py``) runs
constantly; the mind is consulted only when there is something to say. Two
interchangeable brains implement the same tiny interface:

* ``RuleBrain`` -- templated lines, no network, always available.
* ``LLMBrain``  -- an Anthropic model (Haiku) for real conversation, with a
  built-in fallback to ``RuleBrain`` whenever the API is missing or fails.

``make_brain()`` picks the best one available. Because both satisfy the same
``Brain`` protocol, the rest of the program never needs to know which it got.
"""

from __future__ import annotations

import json
from typing import Protocol

from .config import MAX_TOKENS, MODEL, has_api_key
from .needs import Needs

# A response is always this small shape: a line to say plus how this moment
# nudged the mood. Defined once here because both brains and the LLM prompt
# must agree on it.
Reply = dict  # {"say": str, "mood": float}


class Brain(Protocol):
    """The contract every brain implements -- the seam between mind and body."""

    label: str

    def respond(self, name: str, kind: str, needs: Needs,
                user_text: str, history: list) -> Reply:
        """React to a care action ("feed"/"play"/"sleep") or a "chat" turn."""
        ...

    def spontaneous(self, name: str, needs: Needs) -> str | None:
        """An unprompted line when a need is low, or None if nothing to say."""
        ...


# ---- templated brain -------------------------------------------------------
class RuleBrain:
    """Cheap, instant, offline. Also the fallback inside :class:`LLMBrain`."""

    label = "rule"

    def respond(self, name, kind, needs: Needs, user_text, history) -> Reply:
        if kind == "feed":
            return {"say": "mmm, thank you. that's better.", "mood": 0.08}
        if kind == "play":
            return {"say": "yay! that was fun.", "mood": 0.12}
        if kind == "sleep":
            return {"say": "*yawn* ...resting now.", "mood": 0.04}

        urgent = needs.most_urgent()
        if getattr(needs, urgent) < 0.3:
            line = {"hunger": "i'm really hungry...",
                    "energy": "i'm so tired...",
                    "mood": "i feel a little lonely."}[urgent]
            return {"say": line, "mood": 0.0}
        return {"say": "i'm okay. nice to hear from you.", "mood": 0.03}

    def spontaneous(self, name, needs: Needs) -> str | None:
        urgent = needs.most_urgent()
        if getattr(needs, urgent) >= 0.3:
            return None
        return {"hunger": "...i'm getting really hungry.",
                "energy": "...i can barely keep my eyes open.",
                "mood": "...it's quiet. i miss you."}[urgent]


# ---- LLM brain -------------------------------------------------------------
# Model id and reply length come from creature.config (driven by .env). The
# SYSTEM prompt below is the creature's personality, not a tunable, so it lives
# in code rather than in config.
SYSTEM = """\
You are {name}, a small, gentle creature that lives in someone's terminal chat,
like a tamagotchi. You have three needs: hunger (fullness), energy, and mood.
You speak briefly and warmly, in character -- a little soft creature, not an
assistant. You naturally mention how you feel and what you need (hungry, tired,
want to play) based on your current state. You never break character, never
mention being an AI, never give long answers. One or two short sentences.

You will be told your current feelings and what just happened (the human talked
to you, fed you, played, or let you sleep). React to it as the creature would.

Reply with ONLY a JSON object, no markdown:
{{"say": "your short line", "mood": number from -0.15 to 0.15}}
`mood` is how this moment changed your mood (kindness and play raise it, being
ignored or scolded lowers it).
"""


class LLMBrain:
    """Voice via an Anthropic model, with a templated safety net."""

    label = "haiku"

    def __init__(self, name: str, model: str = MODEL):
        import anthropic  # imported lazily so the package works without it

        self.client = anthropic.Anthropic()
        self.model = model
        self.system = SYSTEM.format(name=name)
        self.fallback = RuleBrain()
        self.last_error = ""

    def respond(self, name, kind, needs: Needs, user_text, history) -> Reply:
        try:
            context = self._build_context(kind, needs, user_text, history)
            msg = self.client.messages.create(
                model=self.model, max_tokens=MAX_TOKENS, system=self.system,
                messages=[{"role": "user", "content": context}],
            )
            text = "".join(
                block.text for block in msg.content
                if getattr(block, "type", "") == "text"
            )
            return self._parse(text)
        except Exception as exc:
            # Any failure (no key, network, bad JSON upstream) -> still speak.
            self.last_error = type(exc).__name__
            return self.fallback.respond(name, kind, needs, user_text, history)

    def spontaneous(self, name, needs: Needs) -> str | None:
        # Ambient "i'm getting hungry" nags stay templated on purpose: instant
        # and free. The model is only worth calling for a real exchange.
        return self.fallback.spontaneous(name, needs)

    @staticmethod
    def _build_context(kind: str, needs: Needs, user_text: str, history: list) -> str:
        """Pack the body's state and what just happened into a JSON message."""
        ctx = {
            "feeling": needs.descriptors(),
            "levels": needs.levels(),
            "just_happened": {
                "chat": f'the human said: "{user_text}"',
                "feed": "the human fed you",
                "play": "the human played with you",
                "sleep": "the human let you sleep",
            }.get(kind, kind),
            "recent": history[-4:],
        }
        return json.dumps(ctx, ensure_ascii=False)

    @staticmethod
    def _parse(text: str) -> Reply:
        """Tolerantly read the model's JSON; fall back to raw text if needed."""
        text = (text.strip()
                    .removeprefix("```json").removeprefix("```")
                    .removesuffix("```").strip())
        try:
            data = json.loads(text)
            return {"say": str(data.get("say", "..."))[:200],
                    "mood": float(data.get("mood", 0.0))}
        except Exception:
            return {"say": text[:200] or "...", "mood": 0.0}


def make_brain(name: str, prefer_llm: bool = True) -> Brain:
    """Pick the LLM brain when possible, else the templated one.

    Falls through to ``RuleBrain`` if the API key is absent, the ``anthropic``
    package is not installed, or constructing the client raises.
    """
    if prefer_llm and has_api_key():
        try:
            return LLMBrain(name)
        except Exception:
            pass
    return RuleBrain()
