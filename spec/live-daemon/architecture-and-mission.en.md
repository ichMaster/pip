# pip — Live Daemon: Architecture & Mission

> **Status:** design document, not yet implemented.
> **Scope:** turn pip from a single-process REPL into a resident **pip-server** daemon + a live **pip-client**, with an **asynchronous mind**, **canon LLM chat**, and **session memory**.
> **Track:** *Live Daemon* — **v1** (phases `v1.0`–`v1.5`), a standalone, foundational track that is the substrate for the front-desk vision in [`../vision/pip-frontdesk-spec.md`](../vision/pip-frontdesk-spec.md) (**v2**, the **final target state**).
> **Roadmap:** the global, version-keyed plan is [`../ROADMAP.md`](../ROADMAP.md).
> **Constraint:** the first version stays an **educational project** — standard library only, one concept per module, teaching-quality comments, and guide documentation. See [§9 Educational constraints](#9-educational-constraints).

---

## 1. Mission

pip is a creature that *lives* in your terminal. To truly live, it must keep living **when you look away** — get hungry, get bored, drift in mood, and speak up on its own — not freeze the moment you stop typing.

Today pip only lives while its REPL loop is the foreground process. The moment the loop blocks on input (or on a slow API call), the creature's clock effectively stalls and there is no way to *watch* it change.

This track gives pip three things it needs to be alive:

1. **A heartbeat of its own** — a resident **daemon** (`pip-server`) whose body ticks on real time continuously, with or without anyone attached.
2. **A window you can open** — a **live client** (`pip-client`) that shows the face, mood and needs changing in real time while you talk.
3. **A mind that thinks without holding its breath** — an **asynchronous brain**: the LLM is consulted off the body's clock, so a slow reply never stops the heart.

This is also the **foundation for the final target**: the [front-desk vision](../vision/pip-frontdesk-spec.md) — pip as a concierge to a fleet of agents — *assumes* a pip that is always-on, always-aware, multi-client, and able to speak unprompted. A front-desk cannot live inside a blocking REPL. **Before pip can watch a fleet, pip itself must become a resident daemon with a live window and an async mind. That is this track.**

The first version is still an **educational project**: the daemon, the socket, and the thread pool are introduced as *teaching material* — small, readable, standard-library-only, one concept per file, documented in the guide.

---

## 2. Design principles (unchanged + one new)

The project's identity is the **two-clock design** (see [`creature/__init__.py`](../../creature/__init__.py)): a **BODY** of pure math that ticks on a fast real-time clock, and a **MIND** (the LLM) consulted only when there is something to say. This track keeps that principle and makes it *physical*, then adds one new rule:

| Principle | Before | After (this track) |
|---|---|---|
| **Two clocks** | body & mind in one process, one loop | body clock runs inside the **server**; mind is consulted from it |
| **Body is pure & always-on** | ticks each REPL pass | ticks continuously in the daemon, even with **no client** |
| **Mind only when there's something to say** | called inline, **blocks** the loop | called **off-thread**; never blocks the body or the socket |
| **NEW — body is single-threaded** | (n/a) | the body (`Needs`, history) is mutated **only by the server's main thread**; workers get an immutable snapshot |

That last rule is the safety backbone of the async design: no locks on the body, no data races — see [§5](#5-the-asynchronous-mind-requirement-3).

---

## 3. Process & transport model

```
            ~/.pip/pip.sock  (Unix-domain socket, newline-delimited JSON)
                   │
   ┌── pip-server (daemon) ─────────────────┐        ┌── pip-client (live) ──────┐
   │  owns Pet = Needs(body) + Brain(mind)  │  push  │  reader thread:           │
   │                                        │ ─────▶ │    status / say / thinking│
   │  main thread:                          │        │  main thread:             │
   │    • body clock  (tick on real dt)     │        │    • cbreak keyboard input│
   │    • socket loop (select w/ timeout)   │ ◀───── │    • full-frame redraw    │
   │    • apply finished replies            │  send  │      (face + bars + chat) │
   │  worker pool:                          │ chat/  └───────────────────────────┘
   │    • LLM calls (async, off the clock)  │ act
   │  persistence: ~/.pip/state.json        │        (many clients may attach)
   └────────────────────────────────────────┘
```

- **`pip-server`** — a resident daemon. Owns the one `Pet`. Its **main thread** runs both the body clock and the socket loop; a small **worker pool** runs LLM calls. Persists state to `~/.pip/state.json`.
- **`pip-client`** — a thin, stateless live terminal. It renders what the server pushes and forwards your input. Many clients may attach at once (watch from several panes).
- **Transport** — a **Unix-domain socket** at `~/.pip/pip.sock` (override with `PIP_SOCK`). Chosen because it is bidirectional, local-only, needs no TCP port, and is trivial to `select()` alongside the body clock. Messages are **newline-delimited JSON** — one tiny, forward-compatible contract (see [§4](#4-the-wire-protocol)).

Why a daemon at all? A foreground REPL can do *one* of {wait for input, tick the body, call the API} at a time. A creature that is supposed to be **alive and watchable** needs all three at once. Splitting body (server) from window (client) and pushing the API off-thread is the minimal architecture that delivers it — and it is exactly the shape the front-desk vision needs.

---

## 4. The wire protocol

One small JSON object per line. Deliberately minimal and **forward-compatible** — the front-desk vision adds new message *types* to the same channel, not a new channel.

**server → client**

| `t` | payload | meaning |
|---|---|---|
| `hello` | `{name, brain}` | sent on connect (client learns the creature's name & active brain) |
| `status` | `{levels:{hunger,energy,mood}, state}` | the body changed — pushed on a cadence **and** after every event |
| `say` | `{name, text}` | a spoken line: chat reply, care reply, or spontaneous nag |
| `thinking` | `{}` | a chat/care turn was dispatched to the mind (client shows "…") |
| `bye` | `{}` | the server is shutting down |

**client → server**

| `t` | payload | meaning |
|---|---|---|
| `chat` | `{text}` | talk to pip → routed to the LLM in canon ([§6](#6-canon-chat-requirement-4)) |
| `act` | `{kind: feed\|play\|sleep}` | a care action; numeric effect is applied **immediately** |
| `cmd` | `{name: status\|help}` | `status` triggers a push; `help` is handled locally by the client |
| `shutdown` | `{}` | stop the daemon (optional) |

This **extends** the existing brain contract `{say, mood}` (see [`creature/brain.py`](../../creature/brain.py)): the client never sees `mood` — it is applied on the server, against the body. **Reserved for the vision (no behavior yet):** a `fleet` server→client frame (agent statuses) and `agents` / `dispatch` client→server verbs. They are named here so the protocol does not have to break later.

---

## 5. The asynchronous mind (requirement 3)

The body must keep ticking while the LLM thinks. The rule that makes this safe: **the body is mutated only by the server's main thread.** Workers never touch it; they receive an immutable snapshot and return a reply.

```
client sends {chat,text}
        │
  main thread:  broadcast {thinking}
                ctx = pet.snapshot()          # (copy of Needs, copy of history) — taken on main thread
                pool.submit(pet.think, kind, text, ctx)
        │
  worker thread:  reply = brain.respond(...)  # the slow API call; touches ONLY the snapshot
                  queue.put((kind, text, reply))   # thread-safe handoff
        │
  main thread (next tick):  reply = queue.get()
                            say = pet.apply_reply(kind, text, reply)  # mutate mood + history HERE
                            broadcast {say}, {status}
```

- `Pet.snapshot()` copies `Needs` (a dataclass of floats) and the history list **on the main thread**, so the worker reads a frozen view — no races.
- `Pet.think(kind, text, ctx)` is pure: it calls `brain.respond` against the snapshot and returns `{say, mood}`.
- `Pet.apply_reply(...)` runs back **on the main thread**: it applies the `mood` delta to the live body and appends the turn to history.
- Delivery is a `queue.Queue` drained once per tick; latency ≤ the socket-loop timeout (~0.15 s).
- **Preserved degradations** (from today's design, and important to keep): `LLMBrain.respond` still falls back to `RuleBrain` on any API error; **spontaneous nags stay templated and instant** — they are *not* routed through the API. The async path is only for direct chat and care replies.

Net effect: you feed pip and the bars move *now*; you say something and the bars keep drifting *while* the model writes back — the creature never freezes. This async seam is also what the vision's **dispatch** intent needs (spawning/awaiting an agent is just a slower "think").

---

## 6. Canon chat & session memory (requirements 4 & 5)

- **Canon chat (req 4):** a `chat` message is routed to `LLMBrain` with the existing `SYSTEM` persona in [`creature/brain.py`](../../creature/brain.py) — the soft little-creature voice, JSON `{say, mood}` contract intact. With no API key or `--rule`, it degrades to `RuleBrain` exactly as today. Care actions (`feed`/`play`/`sleep`) also get a canon line via the same async path, *after* their numeric effect lands.
- **Session memory (req 5):** the `Pet` accumulates chat turns for the **whole server session** (not just a REPL run). The LLM context (`_build_context`) includes a **window of recent turns** so pip remembers what you said earlier in the session. Because the server outlives any single client, **memory survives client disconnect/reconnect** within a session. A small cap bounds memory and tokens; a knob (`PIP_HISTORY`) tunes how many turns reach the model. (Durable, cross-session memory is intentionally *out of scope* here — the vision's fleet journal is the long-term store, not chat.)

---

## 7. The live client (requirements 1 & 2)

The client's job: make change **visible in real time** while you type.

- **Rendering reuse:** the client rebuilds a `Needs` from the pushed `levels` and calls the existing pure renderers in [`creature/render.py`](../../creature/render.py) (`status_line`, `face`, `bar`). Rendering stays in one place; payloads stay tiny.
- **Live loop:** a background **reader thread** updates shared UI state (latest status, chat log, "thinking" flag) under a lock; the **main thread** reads the keyboard in `cbreak` mode via `select`, maintains an input buffer, and **redraws the whole frame ~10×/second**. This is what lets the face and bars move while your half-typed line stays intact.
- **Terminal hygiene:** uses the alternate screen buffer (so scrollback is preserved) and restores `termios` on exit. ANSI degrades gracefully, consistent with `render.py`. Unix-only (`select`/`termios`), matching the project's existing platform note.
- **Regions, with room to grow:** `face + needs bars` · `chat log` · `input line`. The layout deliberately leaves space for a future **fleet panel** (vision §8) as a fourth region.

With `--speed > 1` the drift is visible within seconds; at default speed it is a slow, ambient change — exactly the tamagotchi feel, now continuous and watchable.

---

## 8. Module map (what changes)

Each new file is **one concept**, matching the existing package style.

**New**

| File | Concept |
|---|---|
| [`creature/protocol.py`](../../creature/protocol.py) | the wire contract: socket path + newline-JSON framing (`send`, line reader). Pure, no creature logic. |
| [`creature/server.py`](../../creature/server.py) | the daemon: body clock + socket loop + worker pool + broadcast + persistence + (optional) daemonize. |
| [`creature/client.py`](../../creature/client.py) | the live terminal: reader thread + cbreak input + full-frame redraw. |
| [`creature/state.py`](../../creature/state.py) | load/save `state.json` and **age the body by away-time** on startup (mirrors the vision's `core/state.py`). |

**Changed**

| File | Change |
|---|---|
| [`creature/pet.py`](../../creature/pet.py) | add `snapshot()`, `think()`, `apply_reply()`; keep `act()`; document the *body-mutated-only-on-main-thread* contract. |
| [`creature/brain.py`](../../creature/brain.py) | widen the history window in `_build_context` (req 5). No contract change — still `{say, mood}`, fallback preserved, spontaneous stays templated. |
| [`creature/cli.py`](../../creature/cli.py) | subcommands `server` / `client` / `solo`; flags `--detach`, `--name/--speed/--rule`; client auto-spawns a server if none is running. |
| [`creature/chat.py`](../../creature/chat.py) | **unchanged** — kept as `solo` mode (the simple single-process loop, ideal for teaching & offline). |
| [`pip.py`](../../pip.py) · [`creature/__main__.py`](../../creature/__main__.py) | pass subcommands through. |
| [`.env.example`](../../.env.example) · [`CLAUDE.md`](../../CLAUDE.md) | document `PIP_SOCK`, `PIP_HISTORY`, and the new run modes. |

**Untouched on purpose:** [`creature/needs.py`](../../creature/needs.py) (the body is already pure & correct), [`creature/render.py`](../../creature/render.py) (already pure functions, reused by the client).

### Entry points

```
python pip.py server            # foreground daemon (Ctrl-C to stop)
python pip.py server --detach   # double-fork, log to ~/.pip/pip-server.log
python pip.py                    # live client (auto-spawns a server if none)
python pip.py client             # same as above, explicit
python pip.py solo               # the original single-process loop (teaching/offline)
python pip.py --name moss --speed 2 --rule    # flags apply to the server it drives
```

---

## 9. Educational constraints

The first version is teaching material first, software second. Non-negotiables:

- **Standard library only.** No new dependency. `anthropic` stays the single, optional dep. Sockets, `select`, `threading`, `queue`, `termios`, `json` are all stdlib.
- **One concept per module.** `protocol` = framing, `server` = the daemon loop, `client` = the live window, `state` = persistence. No module does two jobs.
- **The two-clock story stays legible.** The daemon must *clarify* the body/mind split, not blur it. The new "body is single-threaded" rule is taught explicitly because it is the crux of safe async.
- **Comments teach the why.** Match the density and tone of the existing modules (see [`creature/chat.py`](../../creature/chat.py), [`creature/pet.py`](../../creature/pet.py)).
- **Docs ship with code.** Each phase extends [`GUIDE_uk.md`](../../GUIDE_uk.md) with a chapter (daemon, socket protocol, async mind, live client) and updates [`CLAUDE.md`](../../CLAUDE.md) and the Ukrainian [`README.md`](../../README.md). The guided tour is part of the deliverable, not an afterthought.
- **`solo` mode is preserved** as the smallest possible teaching path and the offline/smoke-test entry point.

---

## 10. Risks & open decisions

| Topic | Note / decision to make |
|---|---|
| **Portability** | `select` + `termios` + `cbreak` are Unix-only — already a stated project constraint (macOS/Linux). No Windows. |
| **Single instance** | detect an existing daemon by connecting to the socket; clean a **stale** socket file on bind after a crash. |
| **Spontaneous while detached** | when nobody is attached, **queue** nags and flush on connect, or **drop** them? (Queue = friendlier tamagotchi.) — *open* |
| **History growth / tokens** | cap session history; expose `PIP_HISTORY` for the LLM window. Durable memory is deferred to the vision's journal. |
| **Multi-client writes** | many clients may send input; the server serializes everything on the main thread, so it is naturally safe. |
| **Detach vs. foreground** | default `server` runs in foreground (easy to teach & Ctrl-C); `--detach` is the "real daemon" path with a logfile. |

---

## 11. Mapping to the final target (front-desk vision)

This track is **Phase 0 foundation + the seed of Phase 6** of [`../vision/pip-frontdesk-spec.md`](../vision/pip-frontdesk-spec.md). Each piece here is built to be reused, not redone:

| Live-Daemon piece | Serves vision phase |
|---|---|
| `state.json` + away-time aging ([§6 here]) | **Phase 0** — *PIP CORE → state.json* |
| Async mind seam ([§5]) | **Phase 2/3** — concierge **dispatch** is a slower "think"; must be off the body clock |
| Unix-socket protocol ([§4]) | **Phase 5** — the **daemon adapter** (forage over a socket) reuses this transport |
| Resident, always-on body ([§3]) | **Phase 4** — proactive **fleet awareness** needs a process that watches while you are idle |
| Live client regions ([§7]) | **Phase 6** — the **fleet panel** slots in beside face + needs |
| Reserved `fleet`/`agents`/`dispatch` messages ([§4]) | **Phase 1–3** — registry & dispatch verbs land on the same channel |

In one line: **make pip *live* on its own, watchable, and thinking-without-stalling — so that it can later become the front-desk to a whole fleet.**
