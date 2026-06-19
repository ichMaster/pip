# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`pip` is a chat-tamagotchi: a small creature that lives in the terminal. It has needs (hunger, energy, mood) that drain in real time, speaks up about how it feels, and the user both talks to it and cares for it — all in one chat loop. It is an **educational project**: the code is organized to teach a clean architecture, and [GUIDE_uk.md](GUIDE_uk.md) is a guided tour written in Ukrainian for intermediate readers. The user-facing README is also Ukrainian.

Only dependency is an *optional* `anthropic` (for the LLM voice); everything else is the Python standard library.

## Running

```bash
python pip.py                 # needs ANTHROPIC_API_KEY for the LLM voice; otherwise falls back to templates
python -m creature            # equivalent entry point
python pip.py --name moss     # rename the creature
python pip.py --speed 2       # needs drain twice as fast (also speeds spontaneous nags)
python pip.py --rule          # force templated voice, never call the API
```

There is **no build step, no test suite, and no linter configured.** Don't invent commands for them. The only real dependency is `pip install anthropic` (see [requirements.txt](requirements.txt)); without it (or without the API key) the program still runs on templated lines.

To smoke-test the loop non-interactively, pipe commands in and exit with `/quit`:

```bash
printf '/status\nhello\n/feed\n/quit\n' | python pip.py --rule --speed 5
```

Platform note: input uses `select` on `sys.stdin`, so this runs on Unix (macOS/Linux) only, not Windows. The code uses `str.removeprefix`/`removesuffix`, requiring Python 3.9+.

## Layout

[pip.py](pip.py) is a thin launcher; the real code is the [creature/](creature/) package, split so each module is one concept. The `creature` name avoids shadowing the `pip` installer.

| File | Role |
|---|---|
| [creature/needs.py](creature/needs.py) | **BODY** — `Needs`, drain math, descriptors. Pure, no I/O, no LLM. |
| [creature/brain.py](creature/brain.py) | **MIND** — `Brain` Protocol, `RuleBrain`, `LLMBrain`, `make_brain`. |
| [creature/config.py](creature/config.py) | LLM config (`MODEL`, `MAX_TOKENS`, `has_api_key`) loaded from `.env`. |
| [creature/render.py](creature/render.py) | Faces, bars, `status_line` — pure functions of a `Needs`. Sole owner of ANSI/box-drawing (incl. cursor-control primitives: `cursor_up`, `clear_line`, `clear_below`, `save_cursor`/`restore_cursor`, `hide_cursor`/`show_cursor`, `STATUS_HEIGHT`). Faces are a minimal/sparkle set guarded single-width by `is_single_width` (`unicodedata.east_asian_width`). Framing primitives (`box`, `columns`, `welcome_banner`) are width-fed and pure. |
| [creature/pet.py](creature/pet.py) | `Pet` — orchestration; the only place body and mind meet. |
| [creature/chat.py](creature/chat.py) | `run()` — the real-time loop (tick → maybe speak → non-blocking input). Redraws the status block **in place** as a footer (no stacking); owns the cursor arithmetic. Measures the terminal (`shutil.get_terminal_size`) for the welcome banner and the width-aware footer (reflows on resize). |
| [creature/cli.py](creature/cli.py) | `main()` — argparse + wiring. |

## Architecture — the "two-clock" design

The central idea (stated in [creature/__init__.py](creature/__init__.py)): a **BODY** that ticks on a fast clock of pure math, and a **MIND** (the LLM) consulted only when there's something to say. Keep this separation when extending — it's the whole point of the project.

- **Body — `Needs`**: three floats in `[0,1]` where 1 = good (`hunger` stores *fullness*, so every need shares a "higher is better" rule). `advance(dt, speed)` drains them by real elapsed wall-clock time, iterating `DRAIN_PER_SECOND`; everything else just reads state. Deterministic and always runs, independent of any brain.

- **Mind — the `Brain` interface**: `RuleBrain` and `LLMBrain` are interchangeable, both satisfying the `Brain` Protocol (`respond`, `spontaneous`). `make_brain()` returns `LLMBrain` only when `ANTHROPIC_API_KEY` is set *and* `anthropic` imports *and* the client constructs; otherwise `RuleBrain`. Two deliberate degradation paths to preserve when editing:
  - `LLMBrain.respond` wraps the API call in `try/except` and **falls back to its `RuleBrain` (`self.fallback`) on any error** — the creature never crashes or stalls on an API failure.
  - `LLMBrain.spontaneous` **intentionally delegates to `RuleBrain`** — background "I'm getting hungry" nags are always templated (instant, free). The LLM is only consulted for direct user chat and care actions. Don't route spontaneous lines through the API.

- **`Pet`** owns a `Needs` + a `Brain` and is the only place body and mind meet. `act(kind)` applies the numeric effects from the `ACTION_EFFECTS` table (`/feed` `/play` `/sleep`); `respond(kind, text)` asks the brain for a line *and* applies the brain's returned `mood` delta back onto the body. Chat history keeps the last 8 turns; only the last 4 reach the LLM.

- **`run(pet)`** is the loop: tick the body by real `dt`, maybe emit a spontaneous line (rate-limited via `last_spontaneous`, scaled by `speed`), then non-blocking line input via `select.select(..., timeout=0.2)`. `_handle()` decides *what* to say (returns `(lines, quit?)` and applies care effects); `run()` decides *how* to paint it. The status block (face + bars) is a **footer redrawn in place** — `run()` walks the cursor up over the footer, clears, reprints the conversation, repaints the footer (so no stack of stale faces); on idle passes it refreshes the footer in place (via `save_cursor`/`restore_cursor`) only when the rendered status changed, so bars drift live without disturbing typed input. Non-TTY output (`isatty()` false) skips all cursor control and degrades to a plain log; the cursor is restored on exit (`/quit`, EOF, Ctrl-C) via a `finally`. **The two-clock split is unchanged — this is presentation only; the body is never touched here.**

- **Rendering** is pure functions (`face_state`, `face_block`, `bar`, `status_line`) driven entirely by `Needs`. `face_state` is a priority cascade (physical needs beat emotional; `happy` only when euphoric, `content` when merely comfortable, else `ok`). Faces are a Claude-adjacent minimal/sparkle set; every glyph must be **single-width** — `_assert_faces_single_width` runs at import (via `is_single_width`/`unicodedata.east_asian_width`, rejecting Wide/Full/Ambiguous) so a box-smearing glyph fails loudly. A transient **`thinking`** UI state is *not* need-derived (`face_state` never returns it); it's shown only via the optional `state=` override on `face`/`face_block`/`status_line` (default `None` = needs-derived, so existing callers are unaffected), wired live in v0.4. ANSI codes degrade gracefully. `render.py` is the **sole owner of ANSI** — including the cursor-control escape primitives the in-place redraw uses; the *arithmetic* of when/how far to move the cursor lives in `chat.py`. **Framing** (`box`, `columns`, `welcome_banner`, the v0.3 framed UI) stays pure too: the helpers take an explicit `width` and return strings; `chat.py` measures the terminal (`shutil.get_terminal_size`) and feeds width in, recomputing on each redraw so the welcome banner and footer **reflow on resize**. Width-aware `status_line(..., width=...)` keeps the block 4 lines (so `STATUS_HEIGHT` is unchanged); `width=None` is the legacy fixed layout. Scrollback-preserving, **no `curses`/alternate-screen** (a full-frame client is v1.1).

## Configuration (`.env`)

LLM config lives in [creature/config.py](creature/config.py), driven by a git-ignored `.env` at the repo root (template: [.env.example](.env.example)). `config.py` has a tiny stdlib `.env` parser — **no python-dotenv dependency** — that loads the file into `os.environ` on import, *without* overriding variables already set in the real environment (an exported `ANTHROPIC_API_KEY` always wins). Recognized keys: `ANTHROPIC_API_KEY`, `PIP_MODEL` (default `claude-haiku-4-5-20251001`), `PIP_MAX_TOKENS` (default 120). The `SYSTEM` prompt stays in `brain.py` — it's personality, not config. When adding an LLM knob, expose it in `config.py` and document it in `.env.example`.

## LLM contract

`SYSTEM` (in [creature/brain.py](creature/brain.py)) instructs the model to reply with **only** a JSON object `{"say": "...", "mood": <-0.15..0.15>}`. `LLMBrain._parse` strips markdown fences and tolerates non-JSON by falling back to raw text with `mood=0.0`. The model id and reply length come from `config.MODEL` / `config.MAX_TOKENS`. If you change the prompt's output shape, update `_parse` and `Pet.respond` together — they share that `{say, mood}` contract.
