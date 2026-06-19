---
name: upload-issues
description: Upload issues from a phase issues file to GitHub one by one with proper labels and dependencies.
---

# Skill: Upload Phase Issues to GitHub

Upload issues from a phase issues file to GitHub one by one, with proper labels (prefixed by phase) and dependencies.

> Ported from the Lumi project and adapted to pip. pip is an **educational project** with **no test suite and no linter** (see [CLAUDE.md](../../../CLAUDE.md)); this workflow stays lightweight to match.

## Usage

```
/upload-issues <phase-issues-file>
```

Example: `/upload-issues spec/live-daemon/implementation/v1.2-issues.md`

A phase issues file is the fine-grained breakdown of one roadmap phase: each phase (`v1.0`–`v1.5`) in [spec/ROADMAP.md](../../../spec/ROADMAP.md) is split into one or more `PIP-xxx` issues. (The front-desk vision in [spec/vision/pip-frontdesk-spec.md](../../../spec/vision/pip-frontdesk-spec.md) uses `Phase 0`–`Phase 7` the same way.) If the file does not exist yet, derive it from the phase's Goal / Tasks / Acceptance criteria first, then run this skill.

## Instructions

### Step 1: Read the phase issues file

Read the provided file (e.g., `spec/live-daemon/implementation/v1.2-issues.md`).

Determine from the file:
- **Phase id**: from the filename or heading (e.g., `v1.2-issues.md` -> phase = `v1.2`)
- **Label prefix**: `pip::` (shared across the project; the phase lives in `pip::phase:{id}`)

Parse the **Issues Summary Table** to extract for each issue:
- `ID` (e.g., PIP-001)
- `Title`
- `Size` (S, M, L)
- `Area` (the module touched: `needs`, `brain`, `render`, `pet`, `chat`, `cli`, `protocol`, `server`, `client`, `state`, `docs`)
- `Phase` (the roadmap phase it implements, e.g. `v1.2`)
- `Dependencies` (list of PIP-xxx IDs)

Then parse each **detailed issue section** (heading with PIP-xxx) to extract:
- `Description`
- `What needs to be done` (full content)
- `Dependencies`
- `Expected result`
- `Acceptance criteria` (checklist — should align with the phase Acceptance criteria in the roadmap)

### Step 2: Confirm with user

Show the user a summary of what will be created:
- Number of issues
- Label prefix (e.g., `pip::phase:v1.2`)
- Full list of labels that will be created
- Ask for confirmation before proceeding

### Step 3: Create labels (if they don't exist)

Labels use the `pip::` prefix. Phase label format: `pip::phase:{id}`.

Use `gh` to create these labels if they don't already exist (live-daemon phase titles: v1.0 — Transport & process skeleton; v1.1 — Live status & care; v1.2 — Async mind & canon chat; v1.3 — Session memory; v1.4 — Persistence & lifecycle; v1.5 — Vision seams):

```bash
# Phase label
gh label create "pip::phase:v1.2" --color "0E8A16" --description "v1.2 — Async mind & canon chat" 2>/dev/null || true

# Size labels
gh label create "pip::size:S" --color "28A745" --description "Small (a sitting)"  2>/dev/null || true
gh label create "pip::size:M" --color "FFC107" --description "Medium (a day)"     2>/dev/null || true
gh label create "pip::size:L" --color "DC3545" --description "Large (multi-day)"  2>/dev/null || true

# Area labels (one per module touched in this phase)
gh label create "pip::area:server"   --color "1D76DB" 2>/dev/null || true
gh label create "pip::area:client"   --color "0E8A16" 2>/dev/null || true
gh label create "pip::area:protocol" --color "6F42C1" 2>/dev/null || true
gh label create "pip::area:pet"      --color "5319E7" 2>/dev/null || true
gh label create "pip::area:brain"    --color "B60205" 2>/dev/null || true
gh label create "pip::area:docs"     --color "C5DEF5" 2>/dev/null || true
# ... needs / render / chat / cli / state as needed
```

### Step 4: Create issues ONE BY ONE

**IMPORTANT:** Issues must be created one at a time, sequentially. After creating each issue:
1. Show the user the result (issue number, URL)
2. Proceed to the next issue immediately (do not wait for confirmation between issues)

For each issue (in order from the summary table):

1. Build the issue body in markdown:

```markdown
## Description
{description from the detailed section}

## What needs to be done
{full content from the detailed section}

## Dependencies
{dependency list, with references to already-created issue numbers}

## Expected result
{expected result from the detailed section}

## Acceptance criteria
{checklist from the detailed section}

---
**ID:** {PIP-xxx}
**Size:** {S/M/L}
**Phase:** {v1.0..v1.5 or Phase 0..7}
**Area:** {needs/brain/render/pet/chat/cli/protocol/server/client/state/docs}
```

2. Create the issue with a single `gh issue create` command (one issue per command, never batch):

```bash
gh issue create \
  --title "PIP-xxx: {title}" \
  --label "pip::phase:v1.2,pip::size:{S/M/L},pip::area:{area}" \
  --body "$(cat <<'BODY'
{issue body}
BODY
)"
```

3. Record the mapping: PIP-xxx -> GitHub issue #number

4. Report to user: `Created PIP-xxx -> #{number}: {title}`

5. If the issue has dependencies on already-created issues, add a comment:

```bash
gh issue comment {issue-number} --body "Blocked by #{dep-issue-number} (PIP-xxx)"
```

6. Move to the next issue.

### Step 5: Generate report

After all issues are created, generate a report file at:
`spec/live-daemon/implementation/{phase}-github-report.md`

Content:

```markdown
# Phase {id} -- GitHub Issues Report

**Uploaded:** {date}
**Repository:** {github repo URL}
**Total issues:** {count}

## Issue Mapping

| PIP ID | GitHub # | Title | Phase | Labels | URL |
|--------|----------|-------|-------|--------|-----|
| PIP-001 | #5 | Socket framing | v1.0 | pip::phase:v1.0, pip::size:S, pip::area:protocol | {url} |
| ... | ... | ... | ... | ... | ... |

## Labels Created

- pip::phase:{id}
- pip::size:S, pip::size:M, pip::size:L
- pip::area:{list}
```

### Step 6: Report to user

Show the user:
- Total issues created
- Link to the GitHub issues page
- Path to the generated report file

## Error Handling

- If `gh` is not authenticated, tell the user to run `gh auth login`
- If the repo has no GitHub remote yet, tell the user to create one (`gh repo create`) before uploading
- If an issue already exists with the same title, skip it and note in the report
- If label creation fails, continue (labels may already exist)
- On any failure, report what was created so far and what remains
