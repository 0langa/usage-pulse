---
name: pulse:using-pulse
description: Use this skill when explaining Usage Pulse, when checking storage paths, when describing tracked counters, when verifying provider install state, or when diagnosing missing or stale local usage data. Use proactively for Usage Pulse questions.
---

# Using Pulse

## Purpose

Explain and operate Usage Pulse without turning it into billing analytics.
Usage Pulse is local, passive, hook-driven telemetry for Claude Code, Codex,
and Kimi Code sessions.

## Storage

Usage Pulse stores local data under:

```text
~/.usage-pulse/pulse.db
~/.usage-pulse/errors.log
~/.usage-pulse/install-receipt.json
```

It does not store prompt bodies. It stores prompt length, prompt hash, rough
input-token estimate, tool counters, provider identifiers, timestamps, and
project paths.

## Captured Data

Usage Pulse captures:

```text
provider
model id
cwd and git branch
session start/stop timestamps
prompt count
estimated input tokens
tool call count, duration, success, output size
file read/edit/write counts and unique paths
MCP server/tool calls
web search counters
subagent events when provider payloads expose them
hook fires and compaction events
```

It does not capture:

```text
prompt text
cloud billing records
pay-as-you-go dollar cost
remote telemetry
API keys or provider credentials
```

## MCP Tools

Use these report tools:

```text
pulse.today      -> daily totals
pulse.session    -> current or specific session detail
pulse.range      -> bounded date/project/provider totals
pulse.top        -> top tools, MCP servers, agents, or projects
pulse.compare    -> compare current window with previous equal window
pulse.export     -> local json/csv dump
pulse.wipe       -> delete local telemetry after explicit confirmation
```

For an actual usage report, switch to `pulse:usage-report`.

## Install Model

Claude Code loads Usage Pulse as a skills-directory plugin from the Claude
skills directory.

Codex loads Usage Pulse through its personal marketplace and enables
`usage-pulse@personal` in Codex config.

Kimi Code loads Usage Pulse from the Kimi managed plugin directory with an
entry in `~/.kimi-code/plugins/installed.json`.

Plugin hooks and MCP servers should come from bundled plugin manifests. Avoid
duplicating them as global hook or MCP blocks.

## Output Format

For "what is this?" questions:

```text
Usage Pulse is local hook-driven usage telemetry. It records counters, not prompt bodies or cost.
Data lives in ~/.usage-pulse/pulse.db.
Ask for "usage today" or "top tools this week" to query it.
```

For install checks:

```text
Provider | Expected install state | Status
Claude   | Claude skills-directory plugin | ...
Codex    | usage-pulse@personal enabled | ...
Kimi     | installed.json id/root/source entry | ...
```

## Examples

User: "What does Usage Pulse track?"

Response: captured data list, excluded data list, storage path.

User: "Where is my usage data?"

Response:

```text
~/.usage-pulse/pulse.db
```

User: "Does it calculate cost?"

Response:

```text
No. It reports local counters and rough token estimates only.
```

User: "Show my usage today"

Action: switch to `pulse:usage-report` and call `pulse.today`.

## Troubleshooting

If no rows exist, no matching local usage has been captured yet.

If hooks appear broken, check `~/.usage-pulse/errors.log`.

If install state is uncertain, inspect `~/.usage-pulse/install-receipt.json`
and provider plugin registries.

If Kimi reports plugin load errors, inspect
`~/.kimi-code/plugins/installed.json` for malformed entries before launching
new sessions.

If Codex or Claude reports missing MCP tools, verify the plugin manifest points
to bundled `.mcp.json` and the provider has reloaded plugins.

## Related

Use `pulse:usage-report` for concrete reports, comparisons, exports, and
leaderboards.
