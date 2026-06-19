# pip — Roadmap

The arc of the project, by version: from a single creature in your terminal, to
a creature that **lives on its own** and can be watched, to a **front-desk** that
fronts a whole fleet of agents.

- **v0 — Creature** *(shipped)* — the chat-tamagotchi as it is today.
- **v1 — Live Daemon** *(planned)* — pip becomes a resident `pip-server` daemon + a live `pip-client`, with an async mind, canon LLM chat, and session memory. Design: [`live-daemon/architecture-and-mission.en.md`](live-daemon/architecture-and-mission.en.md).
- **v2 — Front-desk for agents** *(future, final target)* — pip as a concierge to a fleet of agents. Design: [`vision/pip-frontdesk-spec.md`](vision/pip-frontdesk-spec.md).

---

## Versioning scheme

```
v{major}.{phase}.{fix}
   │        │       └─ fix    — patch within a phase (bugfix / polish)
   │        └──────────phase  — milestone within the track (minor)
   └───────────────────major  — the track / arc
```

| `major` | Track | Phase range |
|---|---|---|
| **0** | Creature (current) | `v0.0.x` |
| **1** | Live Daemon | `v1.0.x` … `v1.5.x` |
| **2** | Front-desk for agents | `v2.0.x` … `v2.7.x` |

- The **phase** is the unit of planning and release: a finished phase `vA.B` cuts release `A.B.0`; later fixes bump the patch (`A.B.1`, `A.B.2`, …).
- The **phase** is also the GitHub label (`pip::phase:v1.2`) and the issue-file name (`v1.2-issues.md`) that the `/upload-issues` → `/execute-issues` → `/release-version` skills operate on (see [§ Working the roadmap](#working-the-roadmap)).
- **Never change the version without explicit confirmation.**

---

## Version overview

| Version | Theme | Status | Detail |
|---|---|---|---|
| `v0.0.x` | The chat-tamagotchi (two-clock creature) | ✅ shipped | this repo · [CLAUDE.md](../CLAUDE.md) · [GUIDE_uk.md](../GUIDE_uk.md) |
| `v1.0` | Transport & process skeleton | ⬜ planned | [live-daemon/](live-daemon/) |
| `v1.1` | Live status, care & spontaneous voice | ⬜ planned | live-daemon |
| `v1.2` | Asynchronous mind & canon chat | ⬜ planned | live-daemon |
| `v1.3` | Session memory | ⬜ planned | live-daemon |
| `v1.4` | Persistence & daemon lifecycle | ⬜ planned | live-daemon |
| `v1.5` | Forward seams to the front-desk vision | ⬜ planned | live-daemon |
| `v2.0`–`v2.7` | Front-desk for agents (registry → concierge → adapters → fleet → TUI → extension API) | 🔭 future | [vision/](vision/) |

Legend: ✅ shipped · 🟡 in progress · ⬜ planned · 🔭 future.

---

## v0 — Creature *(shipped)* · `v0.0.x`

The current program: a small creature that lives in the terminal chat, with needs that drain in real time and an LLM (or templated) voice.

- **Two-clock design** — a pure-math **BODY** ([`creature/needs.py`](../creature/needs.py)) that ticks on real time, and a **MIND** ([`creature/brain.py`](../creature/brain.py)) consulted only when there's something to say.
- `RuleBrain` / `LLMBrain` behind one `Brain` protocol; LLM falls back to templates on any error; spontaneous nags stay templated.
- Pure rendering ([`creature/render.py`](../creature/render.py)), orchestration ([`creature/pet.py`](../creature/pet.py)), the real-time REPL loop ([`creature/chat.py`](../creature/chat.py)), CLI ([`creature/cli.py`](../creature/cli.py)).
- **Single process, foreground.** The creature only lives while its REPL is the foreground process.

Patches to this line are `v0.0.1`, `v0.0.2`, … This becomes the **`solo`** run-mode once v1 lands.

---

## v1 — Live Daemon *(planned)* · `v1.0` – `v1.5`

> **Goal:** make pip *live on its own*, watchable in real time, and thinking-without-stalling — the foundation the front-desk (v2) stands on.
> **Design & invariants:** [`live-daemon/architecture-and-mission.en.md`](live-daemon/architecture-and-mission.en.md).

This track delivers five changes; they land across the phases below:

| # | Change | Lands in |
|---|---|---|
| 1 | pip is live & changes status independently/constantly, as a **pip-server** daemon | `v1.0` + `v1.1` |
| 2 | **pip-client** updates constantly — you see emotion & status change | `v1.0` + `v1.1` |
| 3 | brain works **async** and sends chat results back to pip-server | `v1.2` |
| 4 | you talk to pip; the answer is from the **LLM in pip canon** | `v1.2` |
| 5 | **session chat history** is added to the prompts | `v1.3` |

**Guardrails (every phase):** runnable after each phase (`solo` keeps working) · **stdlib only** (no new dep; `anthropic` stays the one optional dep) · one concept per new module · **body mutated only on the server's main thread** · preserve degradations (LLM→RuleBrain fallback; spontaneous stays templated/instant) · **docs ship with code** (a [GUIDE_uk.md](../GUIDE_uk.md) chapter + [CLAUDE.md](../CLAUDE.md)/[README.md](../README.md) updates are part of "done").

### v1.0 — Transport & process skeleton
*A server you can start and a client that connects; the body ticks in the daemon with nobody watching.*
- `creature/protocol.py`: socket path (`~/.pip/pip.sock`, `PIP_SOCK`), newline-JSON `send()`, incremental line reader.
- `creature/server.py` (skeleton): bind the Unix socket, accept clients, body clock on real `dt` inside a `select`-with-timeout loop, broadcast `status` on a cadence.
- `creature/client.py` (skeleton): connect, background reader thread, print `status`/`say`.
- `creature/cli.py`: subcommands `server` and `client`; keep `solo` (= today's `chat.run`).
- **Acceptance:** start `pip.py server`; connect with `pip.py client`, see status; disconnect, wait, reconnect → needs are **lower**, proving the body ticked while detached. *(Foundation for req 1.)*
- **Release:** `1.0.0` when the phase is complete.

### v1.1 — Live status, care & spontaneous voice *(req 1 & 2)*
*A continuously-updating window; care actions and unprompted nags visible in real time.*
- Server: push `status` on a cadence **and** after every event; handle `act{feed|play|sleep}` (apply numeric effect at once, then push); route `spontaneous()` nags to all clients.
- Client: full-frame live UI — `cbreak` keyboard input + `select`, input buffer, **~10 Hz redraw**; reuse [`render.py`](../creature/render.py) by rebuilding `Needs` from pushed `levels`; alternate-screen + `termios` restore on exit.
- Client regions: face + needs bars · chat log · input line (leave room for a future fleet panel).
- Client local commands: `/help`, `/status`, `/quit`, `/feed /play /sleep`.
- **Acceptance:** feed → bars jump; idle → bars drift down visibly (clear with `--speed`); a spontaneous nag appears with no input; two clients both update. *(Completes req 1 & 2.)*
- **Release:** `1.1.0`.

### v1.2 — Asynchronous mind & canon chat *(req 3 & 4)*
*Talk to pip and get an in-character LLM reply, with the body never freezing during the call.*
- `creature/pet.py`: add `snapshot()` (copy Needs + history on the main thread), `think(kind, text, ctx)` (pure; calls the brain on the snapshot), `apply_reply(kind, text, reply)` (apply mood delta + append history on the main thread). Document the single-thread-body contract.
- Server: a small `ThreadPoolExecutor`; on `chat`/`act`, broadcast `thinking`, submit `think`, hand the reply back via a `queue.Queue`; drain each tick → `apply_reply` → broadcast `say` + `status`.
- Chat routed to `LLMBrain` (canon `SYSTEM`); preserve LLM→RuleBrain fallback; keep spontaneous templated/instant (not via API).
- **Acceptance:** send a chat line — bars keep moving during the ~1 s call; reply is in pip's voice; `--rule`/no key still works offline; feeding mid-chat behaves. *(Completes req 3 & 4.)*
- **Release:** `1.2.0`.

### v1.3 — Session memory *(req 5)*
*pip remembers the conversation for the whole session.*
- `creature/pet.py`: accumulate chat turns across the session (bounded cap); history appended only in `apply_reply` (main thread).
- `creature/brain.py`: widen `_build_context` to a recent-turns **window**; `PIP_HISTORY` (env) tunes the window size.
- Confirm memory survives client reconnect within one server session.
- **Acceptance:** reference something said earlier → pip recalls it within the session; disconnect/reconnect and the memory is still there. *(Completes req 5.)*
- **Release:** `1.3.0`. **All five requested changes are delivered by the end of this phase.**

### v1.4 — Persistence & daemon lifecycle
*The creature ages across restarts; the daemon behaves like one.*
- `creature/state.py`: save/load `~/.pip/state.json` (needs + timestamp); on startup `advance()` the body by elapsed **away-time**.
- Server: `--detach` (double-fork, log to `~/.pip/pip-server.log`); single-instance guard; clean a stale socket on bind.
- Client: auto-spawn a detached server when none is running, then retry-connect.
- **Acceptance:** restart the server → the creature is **aged, not reset**; a second server is refused cleanly; `pip.py` with no server running just works. *(Realizes the vision's Phase 0 `state.json`.)*
- **Release:** `1.4.0`.

### v1.5 — Forward seams to the front-desk vision
*Leave clean hooks so v2 lands on this substrate without a rewrite. No user-visible behavior change.*
- Protocol: reserve a `fleet` server→client frame and `agents` / `dispatch` client→server verbs (documented, no behavior).
- Client layout: reserve a fourth **fleet panel** region (hidden until populated).
- Finalize the v1→v2 mapping (below) and link it from the vision spec; add a short "From creature to front-desk" appendix to the guide.
- **Acceptance:** named, documented placeholders in protocol & layout; nothing the user sees changes; v2 can start against these seams.
- **Release:** `1.5.0`.

---

## v2 — Front-desk for agents *(future — final target)* · `v2.0` – `v2.7`

pip stops being one creature and becomes a **front-desk**: a catalog of agents, a concierge mind, adapters, and a shared fleet journal — while staying a creature with needs and a voice. Full design: [`vision/pip-frontdesk-spec.md`](vision/pip-frontdesk-spec.md). The phases below map 1:1 to that spec's `Phase 0`–`Phase 7`.

| Version | Phase (vision) | Theme |
|---|---|---|
| `v2.0` | Phase 0 | Refactor groundwork: `state.json`, config + `agents.toml` loader, resolve import/console-name conflict |
| `v2.1` | Phase 1 | Registry (catalog): `Agent` model, `pip agents`, tag match, static help answers |
| `v2.2` | Phase 2 | Concierge mind: intent (chat / help / dispatch / care) + rule fallback + structured action output |
| `v2.3` | Phase 3 | Adapters + dispatch: `AgentAdapter` protocol, subprocess adapter, confirm → run → report |
| `v2.4` | Phase 4 | Fleet awareness: read `fleet/status.json` & journal; mood/restlessness tied to idle/success; proactive voice |
| `v2.5` | Phase 5 | Register `forage` as the first daemon-adapter agent |
| `v2.6` | Phase 6 | TUI: framed face + needs panel + **fleet panel**, live agent statuses, state frames |
| `v2.7` | Phase 7 | Extension API: third-party agents via `agents.toml` + entry points; optional Lumi bridge |

**v1 front-loads several v2 foundations**, so v2 builds on the daemon rather than redoing it — see the mapping in [`live-daemon/architecture-and-mission.en.md` §11](live-daemon/architecture-and-mission.en.md#11-mapping-to-the-final-target-front-desk-vision):

| v1 piece | Serves v2 |
|---|---|
| `state.json` + away-time aging (`v1.4`) | `v2.0` — *PIP CORE → state.json* |
| Async mind seam (`v1.2`) | `v2.2`/`v2.3` — dispatch is a slower "think" |
| Unix-socket protocol (`v1.0`) | `v2.5` — the daemon adapter reuses this transport |
| Resident, always-on body (`v1.0`) | `v2.4` — proactive fleet awareness needs an always-watching process |
| Live client regions (`v1.1`) | `v2.6` — the fleet panel slots in beside face + needs |
| Reserved `fleet`/`agents`/`dispatch` messages (`v1.5`) | `v2.1`–`v2.3` — registry & dispatch verbs on the same channel |

> Note: the vision spec was drafted around a `src/pippet/` re-layout and a `pippet` import name (to avoid clashing with the `pip` installer). That packaging decision is revisited at the start of v2; v1 keeps the existing `creature/` package untouched.

---

## Working the roadmap

The three project skills turn a phase into shipped, tracked work:

1. **`/upload-issues spec/<track>/implementation/<version>-issues.md`** — split a phase into `PIP-xxx` GitHub issues with labels `pip::phase:<version>`, `pip::size:*`, `pip::area:*`. (v1 issue files live under [`live-daemon/implementation/`](live-daemon/); v2 under `vision/implementation/`.)
2. **`/execute-issues pip::phase:<version>`** — implement each issue in dependency order, validate (`py_compile` + the documented smoke-test + acceptance vs. this roadmap), commit one-per-issue, push, close.
3. **`/release-version <A.B.0>`** — when a phase's issues are all done, bump `VERSION`/`README.md`/`RELEASE.txt`, commit, annotated-tag `vA.B.0`, push.

A phase is **not** a single issue — each phase splits into several `PIP-xxx` issues (roughly one per task bullet above). See the skills in [`.claude/skills/`](../.claude/skills/).
