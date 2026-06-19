---
name: execute-issues
description: Execute GitHub issues for a phase sequentially - implement, validate, commit, push, and generate a report.
---

# Skill: Execute GitHub Issues

Execute GitHub issues for a phase sequentially: implement, validate, commit, push, and generate a report.

> Ported from the Lumi project and adapted to pip. pip is an **educational project** with **no test suite, no linter, and no build step** ([CLAUDE.md](../../../CLAUDE.md)). Validation here is therefore `py_compile` + the documented smoke-test + acceptance against the roadmap — **do not invent pytest/ruff/build commands that this project does not have.**

## Usage

```
/execute-issues <label> [--issue PIP-xxx] [--dry-run]
```

The `<label>` is the GitHub phase label exactly as it appears (e.g., `pip::phase:v1.2`).

- `/execute-issues pip::phase:v1.2` -- execute all issues labeled `pip::phase:v1.2`
- `/execute-issues pip::phase:v1.2 --issue PIP-003` -- execute a single issue from that phase
- `/execute-issues pip::phase:v1.2 --dry-run` -- show execution plan without making changes

## Instructions

### Step 0: Verify prerequisites

1. Confirm we are on the expected branch (e.g., `main` or the user's working branch). If on the default branch, branch first per the project's git guidance.
2. Confirm working tree is clean (`git status`)
3. Confirm `gh` is authenticated
4. Parse the label to determine the phase:
   - Label `pip::phase:v1.2` -> phase `v1.2`
5. Fetch issues from GitHub:
   ```bash
   gh issue list --label "{label}" --state open --limit 100
   ```
6. Read the phase issues file for detailed descriptions: `spec/live-daemon/implementation/{phase}-issues.md`
7. If a GitHub report exists (`spec/live-daemon/implementation/{phase}-github-report.md`), read the PIP-to-GitHub# mapping
8. Read [spec/ROADMAP.md](../../../spec/ROADMAP.md) for the phase Goal and Acceptance criteria (the Definition of Done), [spec/live-daemon/architecture-and-mission.en.md](../../../spec/live-daemon/architecture-and-mission.en.md) for the invariants the issue must honor, and [spec/vision/pip-frontdesk-spec.md](../../../spec/vision/pip-frontdesk-spec.md) for the final-target seams an issue should not break.

### Step 1: Build execution queue

From the GitHub issue list, build an ordered queue based on dependencies:
- Parse PIP-xxx IDs from issue titles (format: `PIP-xxx: {title}`)
- Determine dependency order from the phase issues file dependency tree
- Issues with no unmet dependencies go first
- Skip issues already closed on GitHub
- If `--issue PIP-xxx` is specified, execute only that issue (but verify its dependencies are closed)

Show the user the execution plan and ask for confirmation.

### Step 2: Execute each issue (loop)

For each issue in the queue:

#### 2a. Assign and announce

Print: `--- Starting PIP-xxx: {title} ---`

#### 2b. Read issue details

Read the full issue description from the phase issues file (the detailed section for this PIP-xxx).

#### 2c. Implement

Execute the tasks described in the issue. Follow the project conventions in [CLAUDE.md](../../../CLAUDE.md) and the architecture in [spec/live-daemon/architecture-and-mission.en.md](../../../spec/live-daemon/architecture-and-mission.en.md). Route by module:

- **Body changes** ([creature/needs.py](../../../creature/needs.py)): the needs/drain math. Keep it **pure — no I/O, no LLM, no threads**. It must stay deterministic and runnable on its own.
- **Mind changes** ([creature/brain.py](../../../creature/brain.py)): `RuleBrain` / `LLMBrain` behind the `Brain` protocol. Preserve the two deliberate degradations: `LLMBrain.respond` falls back to `RuleBrain` on any API error, and spontaneous nags stay **templated and instant** (never routed through the API). The reply contract is `{say, mood}`; if you change the prompt's output shape, update `_parse` and `Pet.respond`/`apply_reply` together.
- **Rendering changes** ([creature/render.py](../../../creature/render.py)): pure functions of a `Needs`; the sole owner of ANSI/box-drawing. The live client reuses these — don't fork rendering into the client.
- **Orchestration changes** ([creature/pet.py](../../../creature/pet.py)): the one place body and mind meet. For the async mind (v1.2), uphold the invariant: **the body (`Needs`, history) is mutated only on the server's main thread**; workers receive an immutable snapshot and return `{say, mood}`.
- **Transport changes** (`creature/protocol.py`, planned): the newline-JSON wire contract. Keep it small and forward-compatible; the vision's `fleet`/`agents`/`dispatch` messages land on the same channel.
- **Server changes** (`creature/server.py`, planned): the daemon — body clock + socket loop on the main thread, a worker pool for the LLM, broadcast, persistence. The body clock must keep ticking regardless of clients or in-flight API calls.
- **Client changes** (`creature/client.py`, planned): the live terminal — reader thread + cbreak input + full-frame redraw. A thin, stateless window; all body logic stays server-side.
- **State changes** (`creature/state.py`, planned): `state.json` load/save and away-time aging.
- **CLI changes** ([creature/cli.py](../../../creature/cli.py)): subcommands `server`/`client`/`solo` and flag wiring. Keep `solo` (today's [creature/chat.py](../../../creature/chat.py) loop) working.
- **Docs:** every code phase ships a [GUIDE_uk.md](../../../GUIDE_uk.md) chapter and updates [CLAUDE.md](../../../CLAUDE.md) / the Ukrainian [README.md](../../../README.md). Documentation is part of "done."
- **Invariant changes:** any change to a stable seam (the `{say, mood}` brain contract, the wire-protocol message shapes, the single-thread-body rule, the two-clock split) updates [spec/live-daemon/architecture-and-mission.en.md](../../../spec/live-daemon/architecture-and-mission.en.md) (and its `.uk.md` mirror) in the same commit.
- **Stdlib only.** No new dependency — `anthropic` stays the single optional dep. One concept per module. Don't pull later-phase concerns in early ("simplicity first").

#### 2d. Validate

pip has **no pytest/ruff/build** — do not invent them. Run the validation this project actually supports:

1. **Compile/import:** `python -m py_compile {changed_py_files}` and an import check for changed modules (e.g. `python -c "import creature.pet"`).
2. **Smoke-test the loop** (non-interactive, offline, fast), per CLAUDE.md:
   ```bash
   printf '/status\nhello\n/feed\n/quit\n' | python pip.py --rule --speed 5
   ```
   For server/client phases, additionally smoke-test the daemon path the issue introduces (start `pip.py server`, connect a client, exercise the new message, shut down) — keep it scriptable where possible.
3. **Acceptance criteria:** go through each criterion from the issue and verify it against the phase Acceptance criteria in [ROADMAP.md](../../../spec/ROADMAP.md).
4. **Invariant check:** confirm the change did not break the two-clock split, the single-thread-body rule, the `{say, mood}` contract, the LLM→RuleBrain fallback, or the templated/instant spontaneous path.
5. **If a test suite is ever added** to the repo, run it too — but never fabricate one that isn't there.

Record pass/fail for each check. A feature lands only when it compiles, smoke-tests cleanly, and meets its acceptance criteria.

#### 2e. Commit

```bash
git add {specific files created/modified}
git commit -m "$(cat <<'EOF'
PIP-xxx: {title}

{1-2 sentence summary of what was implemented}

Closes #{github-issue-number}

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

#### 2f. Push

```bash
git push
```

#### 2g. Close issue with summary

```bash
gh issue close {issue-number} --comment "$(cat <<'EOF'
## Implementation Summary

**Commit:** {commit-hash}
**Files changed:** {count}

### What was done
{bullet list of key changes}

### Validation
{pass/fail status for each check: py_compile, smoke-test, acceptance, invariants}

### Acceptance criteria
{checklist with pass/fail}
EOF
)"
```

#### 2h. Log progress

Append to the in-memory execution log:
- Issue ID, title
- Commit hash
- Files changed (list)
- Validation results
- Status: success/partial/failed

### Step 3: Handle failures

If implementation or validation fails for an issue:

1. Do NOT commit broken code
2. Stash or revert changes: `git checkout -- .`
3. Add a comment to the GitHub issue explaining what failed
4. Log the failure
5. Ask the user: continue to next issue (if no dependency), or stop?

### Step 3b: Release on completion

**Do NOT bump the version automatically.** Never change the version (VERSION, RELEASE.txt, or git tag) without explicit user confirmation. When a phase's issues are all done, report completion and let the user decide whether/when to release via `/release-version`.

If — and only if — the user confirms a release, delegate to the `/release-version` skill (it owns version files, RELEASE.txt, the commit, the annotated tag, and the push). Suggested mapping: a completed live-daemon phase cuts a minor release (e.g. v1.2 done → `0.2.0`), but the version is the user's call.

If some issues failed or were skipped, do NOT release. Note in the execution report that the phase is incomplete.

### Step 4: Generate execution report

After all issues are processed (or on stop), generate:
`spec/live-daemon/implementation/{phase}-execution-report.md`

```markdown
# Phase {id} -- Execution Report

**Date:** {date}
**Branch:** {branch name}
**Label:** {label}
**Executed by:** Claude Code

## Summary

| Status | Count |
|--------|-------|
| Completed | {n} |
| Failed | {n} |
| Skipped | {n} |
| Remaining | {n} |

## Issues

| # | PIP ID | Title | Phase | Status | Commit | Files | Smoke |
|---|--------|-------|-------|--------|--------|-------|-------|
| 1 | PIP-001 | Socket framing | v1.0 | completed | a1b2c3d | 2 | pass |
| ... | ... | ... | ... | ... | ... | ... | ... |

## Detailed Results

### PIP-001: Socket framing

**Status:** completed
**Commit:** a1b2c3d
**Files changed:**
- `creature/protocol.py` (added)

**Validation:**
- [x] py_compile / import: pass
- [x] Smoke-test: pass
- [x] Acceptance criteria: all pass
- [x] Invariants intact: pass

---

### PIP-002: ...

## Next Steps

{List of remaining issues not yet executed, with their dependencies}
```

Commit and push this report:

```bash
git add spec/live-daemon/implementation/{phase}-execution-report.md
git commit -m "$(cat <<'EOF'
Add {phase} execution report

{n} issues completed, {n} failed, {n} remaining.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
git push
```

## Important Rules

- **One issue at a time.** Never work on multiple issues simultaneously.
- **Dependency order.** Never start an issue whose dependencies are not closed.
- **Clean commits.** Each issue = one commit. No mixing work across issues.
- **No broken code.** Only commit code that compiles, smoke-tests cleanly, and meets its acceptance criteria.
- **Docs ship with the feature.** Every code phase lands with its GUIDE_uk.md chapter and CLAUDE.md/README updates — no "docs later."
- **Two clocks stay separate.** The body is pure and always-on; the mind is consulted only when there's something to say. Don't blur them.
- **Body mutated only on the server's main thread.** Workers get an immutable snapshot; no locks on `Needs`.
- **Preserve degradations.** LLM→RuleBrain fallback on any error; spontaneous nags stay templated and instant (never via the API).
- **Stdlib only.** No new dependency; `anthropic` is the one optional dep. Don't invent pytest/ruff/build commands this project doesn't have.
- **Seams stay stable.** A change to the `{say, mood}` contract, the wire protocol, or the architecture invariants updates the architecture doc (both languages) in the same commit.
- **Ask on ambiguity.** If an issue description is unclear, ask the user rather than guessing.
- **Progress updates.** Print a short status line after each issue completes.
