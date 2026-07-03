---
name: pulse:usage-report
description: Use this skill when answering local Usage Pulse report questions, when the user asks usage today, when comparing date ranges, when grouping by project/provider/tool, or when exporting local usage counters. Use proactively for report requests.
---

# Usage Report

## Purpose

Answer local usage questions from Usage Pulse data. Usage Pulse records local
session counters only; it does not estimate dollar cost and does not fetch cloud
billing data.

## Inputs

Handle natural-language questions such as:

```text
How much did I use today?
How many prompts this week?
What tools did I use most?
Show usage on this project.
Compare this week with last week.
Export my usage since Monday.
```

Resolve relative dates using the current date. State the interpreted date range
when it matters.

## MCP Selection

Call exactly one MCP tool for the first answer.

```text
Today / daily status                  -> pulse.today
Current or named session detail       -> pulse.session
Date range / week / month / project   -> pulse.range
Top tools / MCP / subagents / project -> pulse.top
Trend or versus prior window          -> pulse.compare
Export to file                        -> pulse.export
Delete local usage data               -> pulse.wipe
```

Use `pulse.wipe` only after explicit confirmation from the user.

## Output Format

Put the MCP `summary` first. Then show the smallest useful table.

Daily or provider total:

```text
Provider | Sessions | Prompts | Est. input tokens | Tool calls
```

Project grouping:

```text
Project | Sessions | Prompts | Tool calls | Duration
```

Leaderboard:

```text
Rank | Item | Count | Duration
```

Comparison:

```text
Window | Sessions | Prompts | Tool calls | Change
```

End with this note only when the user asks about tokens or cost:

```text
Token counts are estimates. Usage Pulse does not estimate dollar cost.
```

## Examples

User: "How much did I use today?"

Action:

```text
pulse.today
```

Response: summary, provider/session table, optional token-estimate note.

User: "Top tools this week"

Action:

```text
pulse.top(by="tool", window="7d")
```

Response: ranked tool table.

User: "Usage for this repo since Monday"

Action:

```text
pulse.range(from="<Monday 00:00>", to="<now>", group_by="project")
```

Response: project totals with interpreted date range.

User: "Compare Codex usage this week with last week"

Action:

```text
pulse.compare(window="7d")
```

Response: current window, previous window, and change.

## Constraints

Do not infer pay-as-you-go cost.
Do not ask for cloud billing data.
Do not expose prompt hashes unless the user asks for raw detail.
Do not call more than one MCP tool unless the first result is empty or ambiguous.
Do not save RECALL memories from usage-report work unless the user explicitly asks.

## Troubleshooting

If data is empty, say Usage Pulse has no matching local records.

If a date is vague, choose the nearest normal interpretation and state it.

If the MCP call fails, report the failure briefly and mention
`~/.usage-pulse/errors.log`.

If provider totals look wrong after reinstall, check the provider-specific plugin
install state before blaming captured data.

## Related

Use `pulse:using-pulse` when the user asks what Usage Pulse captures, where it
stores data, or how the plugin works.
