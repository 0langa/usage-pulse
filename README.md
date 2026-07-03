# Usage Pulse

Usage Pulse is local, passive per-session usage telemetry for Claude Code, Codex, and Kimi Code.

It is hook-driven and fail-open. Hooks write local counters to `~/.usage-pulse/pulse.db`, log failures to `~/.usage-pulse/errors.log`, and never block the provider session.

## Privacy

Usage Pulse does not store prompt bodies. It stores prompt length, a SHA-256 hash, and a rough input token estimate. It does not estimate pay-as-you-go dollar cost. It does not sync to cloud and makes no external network calls.

## What It Tracks

- Provider, model id, cwd, git branch, timestamps, duration.
- Prompt count and estimated input tokens.
- Tool call count, duration, success/failure, output bytes.
- Web search count, hashed queries, result counts when present.
- File read/edit/write counts and unique paths touched.
- MCP server/tool calls.
- Subagent invocations when exposed by provider payloads.
- Hook fires and compaction events.

## Install

```powershell
uv sync
uv run python scripts/install.py --provider all
```

The installer copies the plugin into provider plugin locations, writes backups for the small registry files it owns, and records `~/.usage-pulse/install-receipt.json`. Hook and MCP wiring comes from bundled plugin manifests instead of global hook/MCP config blocks.

Uninstall:

```powershell
uv run python scripts/uninstall.py
```

## Provider Assumptions

- Claude Code: installs as a skills-directory plugin under `~/.claude/skills/usage-pulse` with `.claude-plugin/plugin.json`, `hooks/hooks.json`, and bundled MCP.
- Codex: uses `.codex-plugin/plugin.json`, `~/.agents/plugins/marketplace.json`, and a minimal plugin enable block in `~/.codex/config.toml`. Bundled hooks/MCP stay inside the plugin.
- Kimi Code: installs under `~/.kimi-code/plugins/managed/usage-pulse` and records one `id/root/source/enabled` entry in `~/.kimi-code/plugins/installed.json`.

## MCP Tools

All tools return structured JSON with a human-readable `summary` field.

### `pulse.today`

Returns today's totals and per-session breakdown.

```json
{
  "summary": "1 sessions, 3 prompts, 4 tool calls, 120 est. input tokens.",
  "from": "2026-07-03T00:00:00+00:00",
  "to": "2026-07-03T10:00:00+00:00",
  "totals": {},
  "groups": []
}
```

### `pulse.session`

Arguments:

```json
{ "id": "current" }
```

Returns one detailed session with grouped tools, MCP calls, file ops, unique paths, and web searches.

### `pulse.range`

Arguments:

```json
{ "from": "2026-07-01T00:00:00Z", "to": "2026-07-03T23:59:59Z", "group_by": "day" }
```

`group_by` can be `day`, `provider`, or `project`.

### `pulse.top`

Arguments:

```json
{ "by": "tool", "limit": 10, "window": "7d" }
```

`by` can be `tool`, `mcp`, `agent`, or `project`.

### `pulse.compare`

Arguments:

```json
{ "window": "7d" }
```

Compares the selected window with the prior equal-length window.

### `pulse.export`

Arguments:

```json
{ "format": "json", "to": "C:\\Users\\you\\usage-pulse.json", "from": "2026-07-01T00:00:00Z", "until": "2026-07-03T00:00:00Z" }
```

`format` can be `json` or `csv`.

### `pulse.wipe`

Arguments:

```json
{ "confirm": true }
```

Deletes local telemetry rows.

## Development

```powershell
uv sync --group dev
uv run ruff check .
uv run mypy src scripts tests
uv run pytest
```
