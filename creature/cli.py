"""Command-line entry point: parse flags, wire up the parts, run the loop."""

from __future__ import annotations

import argparse

from .brain import make_brain
from .chat import run
from .pet import Pet
from .render import CYAN, RESET


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="pip -- a chat tamagotchi.")
    parser.add_argument("--name", default="pip", help="what to call the creature")
    parser.add_argument("--speed", type=float, default=1.0, help="how fast needs drain")
    parser.add_argument("--rule", action="store_true",
                        help="force the templated voice (never call the API)")
    args = parser.parse_args(argv)

    brain = make_brain(args.name, prefer_llm=not args.rule)
    pet = Pet(args.name, brain, speed=args.speed)
    try:
        run(pet)
    except (KeyboardInterrupt, EOFError):
        print(f"\n  {CYAN}{args.name}{RESET}: oh... bye.")
