# Journal Agent

Background agent for org-mode journal carry-forward, daily template generation,
stale-TODO detection, and weekly review drafting.

## Overview

The `journal-agent` operates on `~/Journal/daily/YYYY-MM-DD.org` files and
`~/Journal/weekly/` review files. It runs four tasks, selectable via `--task`.

## Tasks

| Task | What it does |
|---|---|
| `carry-forward` | Reads yesterday's (or `--date`) daily file, extracts all unchecked `- [ ]` items and `* TODO` headlines |
| `template-gen` | Creates tomorrow's daily entry (or appends to it) with a `* Carry Over` section pre-populated from carry-forward |
| `stale-check` | Scans the last N days; flags any TODO that has appeared unchecked for 3+ consecutive days |
| `weekly-review` | Drafts `~/Journal/weekly/YYYY-WNN.org` from the current week's daily entries |
| `all` | Runs carry-forward + template-gen + stale-check (default) |

## Usage

```bash
# Run all three daily tasks (carry yesterday → tomorrow's template + stale alert)
afs agents run journal-agent

# Carry-forward only, pretty JSON output
afs agents run journal-agent -- --task carry-forward --pretty

# Generate tomorrow's template from a specific source date
afs agents run journal-agent -- --task template-gen --date 2026-03-20

# Stale-check with custom window and threshold
afs agents run journal-agent -- --task stale-check --scan-days 21 --stale-threshold 4

# Draft this week's review
afs agents run journal-agent -- --task weekly-review

# Draft a specific week (overwrite if it already exists)
afs agents run journal-agent -- --task weekly-review --week 2026-W12 --overwrite

# Write JSON report to a file
afs agents run journal-agent -- --output ~/.afs/reports/journal.json
```

## Arguments

| Flag | Default | Description |
|---|---|---|
| `--task` | `all` | Which task(s) to run (see table above) |
| `--date` | yesterday | Source date for carry-forward (`YYYY-MM-DD`) |
| `--week` | current week | ISO week for weekly-review (`YYYY-WNN`) |
| `--daily-dir` | `~/Journal/daily` | Override daily journal directory |
| `--weekly-dir` | `~/Journal/weekly` | Override weekly journal directory |
| `--scan-days` | `14` | History window for stale-check |
| `--stale-threshold` | `3` | Consecutive-day streak to count as stale |
| `--overwrite` | off | Replace existing files instead of skipping/appending |
| `--output` | — | Write JSON result to this path |
| `--stdout` | — | Force JSON to stdout even when non-interactive |
| `--pretty` | — | Pretty-print JSON output |
| `--quiet` | — | Suppress INFO logs |

## Org-mode parsing

Recognized as **unchecked**:
- `- [ ] item text` (any leading indent)
- `* TODO item text` / `** TODO item text`

Recognized as **done** (wins):
- `- [x] item text` / `- [X] item text`
- `* DONE item text`

Both forms are normalized to `- [ ] text` when written to Carry Over sections.

## Stale-TODO detection

For each TODO text, the agent tracks the longest *current* consecutive streak
(streak that ends yesterday or today). Items with a streak ≥ `--stale-threshold`
are reported in `payload.stale_check.stale_todos`, sorted longest-streak-first.

Example stale entry:
```json
{
  "todo": "- [ ] Finish V2/V3 postmortem",
  "streak_days": 5,
  "first_seen": "2026-03-15",
  "last_seen": "2026-03-19"
}
```

## Weekly review output format

```org
#+TITLE: Weekly Review — 2026-W12 (Mar 10–16)
#+AUTHOR: AFS

* Wins
- ...

* Misses
- ...

* Carry Over
- [ ] ...

* Top 3 for Next Week
1.
2.
3.
```

Wins are populated from `- [x]` items, `* DONE` headlines, and narrative bullets
from `* Work` / `* AFS / Side Projects` sections. The user should curate before
publishing.

Misses are items that appeared as unchecked during the week but are absent from
the final day's carry-over (silently dropped without completion).

## JSON result shape

```json
{
  "name": "journal-agent",
  "status": "ok",
  "task": "journal:all",
  "metrics": {
    "carry_forward_count": 3,
    "template_items_added": 3,
    "stale_count": 1
  },
  "notes": [
    "template: created → /Users/…/2026-03-22.org",
    "STALE: 1 TODO(s) unchecked for 3+ days — \"- [ ] Write postmortem\""
  ],
  "payload": {
    "carry_forward": { "found": true, "todo_count": 3, "items": [...] },
    "template_gen": { "action": "created", "items_added": 3, "path": "..." },
    "stale_check": { "stale_count": 1, "stale_todos": [...] }
  }
}
```
