---
name: pulse:usage-report
description: Use this skill when the user asks how much they used today, this week, in a date range, or on a project. Call exactly one Usage Pulse MCP tool, then format the structured result.
---

# Usage Report

## Input

Receive a natural-language usage question, such as:

- "How much did I use today?"
- "How many prompts this week?"
- "What tools did I use most?"
- "Show usage on this project."
- "Compare this week with last week."

## MCP Selection

Call exactly one MCP tool.

Use `pulse.today` for today's totals or a general daily status question.

Use `pulse.session` for current-session or specific-session detail.

Use `pulse.range` for date ranges, this week, this month, or project/provider grouping.

Use `pulse.top` for leaderboards by tool, MCP server/tool, subagent, or project.

Use `pulse.compare` for "versus last week", "up or down", or trend questions.

Use `pulse.export` only when the user asks for a file dump.

Use `pulse.wipe` only after explicit wipe/delete confirmation.

## Output Format

Put the MCP `summary` first.

Then show the smallest useful table.

Use columns that match the question:

```text
Provider | Sessions | Prompts | Est. input tokens | Tool calls
```

For project grouping:

```text
Project | Sessions | Prompts | Tool calls | Duration
```

For leaderboards:

```text
Rank | Item | Count | Duration
```

End with one short note only when useful:

```text
Token counts are estimates. Usage Pulse does not estimate dollar cost.
```

## Examples

User: "How much did I use today?"

Action: call `pulse.today`.

Response: summary first, then per-session/provider totals.

User: "Top tools this week"

Action: call `pulse.top` with `by="tool"` and `window="7d"`.

Response: leaderboard table.

User: "Usage for this repo since Monday"

Action: call `pulse.range` with date bounds and `group_by="project"`.

Response: project table.

## Constraints

Do not infer pay-as-you-go cost.

Do not ask for cloud data.

Do not expose prompt hashes unless user asks for raw detail.

Do not call more than one MCP tool unless first result is empty or ambiguous.

## Troubleshooting

If data is empty, say Usage Pulse has no matching local records.

If a date is vague, choose the nearest normal interpretation and state it.

If the MCP call fails, report the failure briefly and mention `~/.usage-pulse/errors.log`.

## Related

See `pulse:using-pulse` for what Usage Pulse captures and where it stores data.
