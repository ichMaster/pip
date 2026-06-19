#!/usr/bin/env python3
"""pip -- a chat tamagotchi. Thin launcher.

A small creature that lives in your terminal chat. It has needs (hunger,
energy, mood) that drain in real time, speaks up about how it feels, and you
both talk to it and care for it -- all in the same chat. Its voice is an
Anthropic model (Haiku); with no API key it falls back to templated lines so it
always runs.

    pip install anthropic
    export ANTHROPIC_API_KEY=...
    python pip.py
    python pip.py --name moss --speed 2 --rule

The implementation lives in the `creature` package, split by concept:

    creature/needs.py   the BODY  -- needs drain on a real-time clock (pure math)
    creature/brain.py   the MIND  -- templated + LLM voices behind one interface
    creature/render.py  the face and bars (pure functions of the body)
    creature/pet.py     orchestration -- where body and mind meet
    creature/chat.py    the real-time loop
    creature/cli.py     flags + startup

See GUIDE_uk.md for a guided tour of the architecture.
"""

from creature.cli import main

if __name__ == "__main__":
    main()
