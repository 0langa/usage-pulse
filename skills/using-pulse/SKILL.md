---
name: pulse:using-pulse
description: Session-start primer for Usage Pulse. Use when the user asks what Usage Pulse does or how to query it.
---

# Using Pulse

Usage Pulse records local session counters through hooks.

It stores data in `~/.usage-pulse/pulse.db`.

It never stores prompt bodies.

It stores prompt length, prompt hash, and rough input token estimate.

It never estimates dollar cost.

It never syncs to cloud.

It exposes MCP tools:

- `pulse.today`
- `pulse.session`
- `pulse.range`
- `pulse.top`
- `pulse.compare`
- `pulse.export`
- `pulse.wipe`

Use `pulse.today` for quick daily status.

Use `pulse.session(id="current")` for current session detail.

Use `pulse.range(group_by="project")` for project totals.

Use `pulse.top(by="tool")` for tool leaderboards.

Use `pulse.compare(window="7d")` for trend deltas.

Use `pulse.export(format="json"|"csv")` for local dumps.

Use `pulse.wipe(confirm=true)` only after explicit user confirmation.

If hooks fail, they log to `~/.usage-pulse/errors.log` and allow the provider session to continue.

Treat all token numbers as estimates.

Do not report PAYG cost.
