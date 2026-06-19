"""LLM configuration, loaded from a ``.env`` file with safe defaults.

Everything that tunes the creature's voice lives here, in one place: which
model speaks, how long a reply may be, and the API key. Values come from the
environment; a local, git-ignored ``.env`` next to ``pip.py`` is read into the
environment on import, so your key stays out of the shell history and out of
version control.

There is no python-dotenv dependency -- this is a tiny, forgiving parser. It
never overrides a variable already set in the real environment, so an exported
``ANTHROPIC_API_KEY`` always wins over the file.
"""

from __future__ import annotations

import os
from pathlib import Path


def _candidate_paths() -> list[Path]:
    """Where to look for a .env: the working dir, then the project root."""
    project_root = Path(__file__).resolve().parent.parent
    return [Path.cwd() / ".env", project_root / ".env"]


def _load_dotenv() -> None:
    """Read the first .env we find into os.environ (without clobbering)."""
    for path in _candidate_paths():
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip().removeprefix("export ").strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # Skip blanks (a placeholder in .env is a no-op) and never override
            # a value already present in the real environment.
            if key and value and key not in os.environ:
                os.environ[key] = value
        return


_load_dotenv()

# ---- the LLM knobs, read after .env is loaded ------------------------------
DEFAULT_MODEL = "claude-haiku-4-5-20251001"  # Anthropic Haiku

#: Which Anthropic model voices the creature (env: PIP_MODEL).
MODEL = os.environ.get("PIP_MODEL", DEFAULT_MODEL)

#: Max tokens per reply -- lines are short, so keep this small (env: PIP_MAX_TOKENS).
MAX_TOKENS = int(os.environ.get("PIP_MAX_TOKENS", "120"))


def has_api_key() -> bool:
    """True if an Anthropic key is available, so the LLM voice can be used."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))
