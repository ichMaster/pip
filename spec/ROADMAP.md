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
| **0** | Creature (current) | `v0.0.x` … `v0.4.x` |
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
| `v0.1` | Stable status picture (in-place) | ⬜ planned | [creature/chat.py](../creature/chat.py) |
| `v0.2` | Claude-style face set | ⬜ planned | [creature/render.py](../creature/render.py) |
| `v0.3` | Framed UI redesign (welcome banner & panels) | ⬜ planned | [creature/render.py](../creature/render.py) |
| `v0.4` | Async brain (off-thread) | ⬜ planned | [creature/brain.py](../creature/brain.py) · [chat.py](../creature/chat.py) |
| `v1.0` | Transport & process skeleton | ⬜ planned | [live-daemon/](live-daemon/) |
| `v1.1` | Live status, care & spontaneous voice | ⬜ planned | live-daemon |
| `v1.2` | Asynchronous mind & canon chat | ⬜ planned | live-daemon |
| `v1.3` | Session memory | ⬜ planned | live-daemon |
| `v1.4` | Persistence & daemon lifecycle | ⬜ planned | live-daemon |
| `v1.5` | Forward seams to the front-desk vision | ⬜ planned | live-daemon |
| `v2.0`–`v2.7` | Front-desk for agents (registry → concierge → adapters → fleet → TUI → extension API) | 🔭 future | [vision/](vision/) |

Legend: ✅ shipped · 🟡 in progress · ⬜ planned · 🔭 future.

---

## v0 — Creature · `v0.0` – `v0.4`

The base creature: a small thing that lives in the terminal chat, with needs that drain in real time and an LLM (or templated) voice. **`v0.0` is shipped**; `v0.1`–`v0.4` polish the single-process experience *before* the v1 daemon. **Same guardrails as v1** — stdlib only, one concept per change, preserve the two-clock split and the LLM→RuleBrain fallback, and **docs ship with code**.

### v0.0 — The two-clock creature *(shipped)*
- **BODY** ([`creature/needs.py`](../creature/needs.py)) ticks on real time; **MIND** ([`creature/brain.py`](../creature/brain.py)) is consulted only when there's something to say.
- `RuleBrain` / `LLMBrain` behind one `Brain` protocol; LLM falls back to templates on any error; spontaneous nags stay templated.
- Pure rendering ([`creature/render.py`](../creature/render.py)), orchestration ([`creature/pet.py`](../creature/pet.py)), the real-time REPL loop ([`creature/chat.py`](../creature/chat.py)), CLI ([`creature/cli.py`](../creature/cli.py)).
- **Single process, foreground**; bugfix/polish patches are `v0.0.1`, `v0.0.2`, … This becomes the **`solo`** run-mode once v1 lands.

### v0.1 — Stable status picture *(requirement 2)*
*Goal: the face + needs are one **persistent picture that updates in place** (like Claude Code's stable UI), not a fresh face block printed after every turn.*

Today `run()` / `_handle` re-`print(status_line(…))` each interaction, so the terminal fills with a stack of stale faces.
- Keep a **fixed status region** and redraw it in place with ANSI cursor control (cursor-up + clear-line, or save/restore), so the face/bars update without scrolling.
- Chat lines scroll as normal; only the status block is redrawn. Refresh on a cadence (each loop pass / on change) so drain is visible live without spamming output.
- Degrade gracefully where ANSI is ignored (fall back to an occasional reprint).
- Pure render functions in [`render.py`](../creature/render.py) stay unchanged — this is loop/presentation work in [`chat.py`](../creature/chat.py).
- **Acceptance:** across a session the face stays as one updating picture (no stack of old faces); feeding/talking updates it in place; bars visibly drift (clear with `--speed`).
- **Forward link:** precursor to `v1.1`'s live-client full-frame redraw.
- **Release:** `0.1.0`.

### v0.2 — Claude-style face set *(requirement 3)*
*Goal: several faces in a cleaner, Claude-adjacent aesthetic (the sparkle / minimal look), replacing the current ASCII set.*

Today [`render.py`](../creature/render.py) has five faces (happy / ok / hungry / tired / sad) built from ASCII eyes + mouth.
- Design a richer set of faces styled close to Claude Code's minimal look (e.g. the `✻`/`✶` sparkle motif), keeping **single-width glyphs** so the box stays aligned (verify width — many sparkle glyphs render double-width in some terminals).
- Map states via the existing `face_state` cascade; consider adding states (e.g. `content`, `playful`) and a **`thinking` face** for v0.4's pending-reply state.
- Update `FACE_PARTS` / `STATE_FACE` / `STATE_COLOR`; keep rendering pure and ANSI-degrading.
- Refresh any face samples in [`GUIDE_uk.md`](../GUIDE_uk.md) / [`README.md`](../README.md).
- Illustrative direction (final glyphs designed in this phase):
  ```
  content  ╭───────╮      thinking ╭───────╮
           │ ✶   ✶ │               │ ✻   ✻ │
           │  ‿‿‿  │               │   ·   │
           ╰───────╯               ╰───────╯
  ```
- **Acceptance:** the creature shows several distinct, on-brand faces; box alignment holds across states; a thinking face appears during async replies; both `--rule` and LLM paths render them.
- **Release:** `0.2.0`.

### v0.3 — Framed UI redesign *(new)*
*Goal: a cleaner, Claude-Code-adjacent presentation — a width-aware welcome banner and framed, colored panels — while keeping the natural-scrollback chat model (no full-screen takeover).*

Today the UI is a face block + three needs bars ([`status_line`](../creature/render.py)) drawn as an in-place footer (v0.1) — there is no welcome banner, no boxed/columned panels, and the layout is a fixed width regardless of terminal size.
- Add a **welcome banner** on startup: a bordered, colored box (reuse the box-drawing already in [`render.py`](../creature/render.py)) with a two-column layout (e.g. greeting | quick-help), styled close to Claude Code's framed panels.
- Make the frame **width-aware** via stdlib `shutil.get_terminal_size()` (no new dependency) so boxes/panels fill the terminal and degrade on narrow widths; recompute on redraw.
- Keep it all as **pure render functions** in [`render.py`](../creature/render.py) (the sole ANSI owner); [`chat.py`](../creature/chat.py) only places them. Glyphs stay **single-width** (the import-time width assertion still guards the box); ANSI still degrades where ignored.
- **Preserve the scrollback chat model** — conversation scrolls in the normal terminal; the status stays an in-place footer. **No `curses`/alternate-screen TUI** at this stage; a full-screen frame is the `v1.1`/`v2.6` client, not v0.
- Refresh the UI samples in [`GUIDE_uk.md`](../GUIDE_uk.md) / [`README.md`](../README.md).
- **Acceptance:** startup shows a framed, colored welcome banner; panels are boxed and aligned; resizing the terminal reflows the frame (boxes fit the width, no smearing); piped/non-TTY output degrades to a plain log; the two-clock split and footer behavior are unchanged.
- **Forward link:** the visual groundwork for `v1.1`'s live full-frame client and `v2.6`'s framed fleet TUI — raw-ANSI and scrollback-preserving here, not a screen takeover.
- **Release:** `0.3.0`.

### v0.4 — Async brain (off-thread) *(requirement 1)*
*Goal: the LLM reply no longer freezes the loop — the body keeps ticking and pip can show it's thinking.*

Today [`chat.py`](../creature/chat.py) calls `pet.respond("chat", …)` synchronously inside `_handle`, so the whole `run()` loop blocks for the ~1 s of an API call: the body clock stalls and input goes dead.
- Run the brain call on a **background thread** (`threading` / `concurrent.futures`); the main loop keeps ticking the body and polling input.
- Deliver the result back via a `queue.Queue`; apply the mood delta + append history **on the main thread** (keep the body single-threaded — the same invariant `v1.2` reuses, introduced here in miniature).
- While a reply is pending, show the **`thinking` face** (v0.2) in the **stable picture** (v0.1); swap to the reply when it lands.
- Unchanged: spontaneous nags stay templated/instant; `LLMBrain`→`RuleBrain` fallback; `--rule` stays instant.
- **Acceptance:** send a chat line — the status/body keeps updating during the call (no freeze); the reply appears when ready; `Ctrl-C` still works; `--rule` unaffected.
- **Forward link:** the single-process seed of `v1.2`'s daemon worker-pool async mind. *(A separate brain **process** is the v1 daemon, not v0 — v0.4 is off-thread, not off-process.)*
- **Release:** `0.4.0`.

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
- **Interaction state machine** (server, main thread): a small, explicit `IDLE → THINKING → IDLE` machine layered over the existing `thinking` render seam (the `state=` override in [`render.py`](../creature/render.py), from v0.2). It makes the interleavings the daemon now allows well-defined: a `chat` arriving while `THINKING` is **enqueued (FIFO)**, never dispatched as a second concurrent call; a care `act` applies its numeric effect immediately in **any** state; a spontaneous nag is **suppressed while `THINKING`**. The machine is what emits the `thinking`/`say` frames and selects the face state. **It lives on the interaction layer only — the body (`Needs`) is continuous drain, never a state — so the two-clock split is preserved.**
- Chat routed to `LLMBrain` (canon `SYSTEM`); preserve LLM→RuleBrain fallback; keep spontaneous templated/instant (not via API).
- **Acceptance:** send a chat line — bars keep moving during the ~1 s call; reply is in pip's voice; `--rule`/no key still works offline; feeding mid-chat behaves; a second chat sent mid-think **queues** (no concurrent call) and a spontaneous nag never interrupts a pending reply. *(Completes req 3 & 4.)*
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

1. **`/upload-issues spec/<track>/implementation/<version>-issues.md`** — split a phase into `PIP-xxx` GitHub issues with labels `pip::phase:<version>`, `pip::size:*`, `pip::area:*`. (v0 issue files live under `v0/implementation/`; v1 under [`live-daemon/implementation/`](live-daemon/); v2 under `vision/implementation/`.)
2. **`/execute-issues pip::phase:<version>`** — implement each issue in dependency order, validate (`py_compile` + the documented smoke-test + acceptance vs. this roadmap), commit one-per-issue, push, close.
3. **`/release-version <A.B.0>`** — when a phase's issues are all done, bump `VERSION`/`README.md`/`RELEASE.txt`, commit, annotated-tag `vA.B.0`, push.

A phase is **not** a single issue — each phase splits into several `PIP-xxx` issues (roughly one per task bullet above). See the skills in [`.claude/skills/`](../.claude/skills/).
