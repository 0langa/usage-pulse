---
name: pulse:using-pulse
description: Use this skill when the user asks what Usage Pulse does, where it stores data, what it tracks, or how to query local usage reports.
---

# Using Pulse

## Primer

Usage Pulse records local session counters through hooks.
It stores data in `~/.usage-pulse/pulse.db`.
It never stores prompt bodies.
It stores prompt length, prompt hash, and rough input token estimate.
It never estimates dollar cost.
It never syncs to cloud.
It exposes MCP tools:
It logs hook failures to `~/.usage-pulse/errors.log`.

## Captured Data

It captures provider, model, cwd, git branch, timestamps, and duration.
It counts prompts and estimates input tokens.
It records tool calls, duration, success/failure, and output size.
It records file read/edit/write counts and unique paths.
It records MCP calls, web searches, subagents, hooks, and compactions.

## MCP Tools

- `pulse.today`
- `pulse.session`
- `pulse.range`
- `pulse.top`
- `pulse.compare`
- `pulse.export`
- `pulse.wipe`

## Query Rules

Use `pulse.today` for quick daily status.
Use `pulse.session(id="current")` for current session detail.
Use `pulse.range(group_by="project")` for project totals.
Use `pulse.top(by="tool")` for tool leaderboards.
Use `pulse.compare(window="7d")` for trend deltas.
Use `pulse.export(format="json"|"csv")` for local dumps.
Use `pulse.wipe(confirm=true)` only after explicit user confirmation.

## Constraints

Treat all token numbers as estimates.
Do not report PAYG cost.
Do not imply cloud sync.
Do not show prompt hashes unless user asks for raw detail.

## Example

```text
User: how much did I use today?
Action: call pulse.today
Output: summary first, then compact totals
```

## Troubleshooting

If no rows exist, say no local usage has been captured yet.
If hooks appear broken, check `~/.usage-pulse/errors.log`.
If install state is uncertain, check `~/.usage-pulse/install-receipt.json`.
