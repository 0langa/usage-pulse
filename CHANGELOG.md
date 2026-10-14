# Changelog

## [0.1.11] - 2026-10-15

- Tool-call durations now use the tool time the host reports in the hook payload (Claude Code's `duration_ms`), so permission prompts and hook startup no longer count. Without it, the duration is the time between the PreToolUse and PostToolUse events, taken from the payloads' own timestamps when they carry one.
- Payload timestamps are stored as UTC ISO 8601 and may be ISO strings or Unix seconds or milliseconds. Before, a numeric timestamp made the hook event fail.
- Upgrade note: on its first run after the upgrade, the database merges the duplicate tool-call rows recorded before 0.1.10 (an open "started" row plus a separate completed row per call), so top-tool and per-session tool counts stop counting those calls twice. This runs once, keeps every completed call and leaves session totals unchanged. Calls already stored as one row, including fast calls whose two events carry the same host timestamp, are left as they are, and repaired rows keep the 0 ms duration they were recorded with.
- The install test no longer runs the real `codex plugin add`, so running the test suite cannot register the plugin in your real `~/.codex`.

## [0.1.10] - 2026-10-14

- Fix tool-call telemetry for Claude Code and Codex: hooks now pair PreToolUse and PostToolUse by the `tool_use_id` both hosts send and read the `tool_response` output, so each call records one row with its real duration and output size instead of an orphan "started" row plus a 0 ms, 2-byte row.
- Lock patched versions of four transitive dependencies (pyjwt 2.15.0, urllib3 2.8.0, anyio 4.14.2, cryptography 50.0.0) to clear their known advisories. Direct dependency ranges are unchanged.

## [0.1.9] - 2026-09-09

- Fix MCP dispatch for `pulse.range` and `pulse.export` by accepting the public `from` argument while passing Python's `from_` parameter internally.
- Exercise filtered and default range/export calls through FastMCP dispatch in regression coverage.

## [0.1.8] - 2026-08-05

- Pending release notes.

## [0.1.7] - 2026-08-05

- Aligned runtime and legacy manifest version metadata with generated provider manifests.
- Added regression coverage for provider install-version parity.

## [0.1.6] - 2026-07-27

- Fixed the Claude Code MCP server failing to start with `ModuleNotFoundError: No module named 'usage_pulse'`. Claude Code launches plugin MCP servers from the session working directory, so the relative `--project .` pointed at the user's repo instead of the cached plugin. Both `--project` and `cwd` now use `${CLAUDE_PLUGIN_ROOT}`.
- Codex and Kimi MCP configs are unchanged.

## [0.1.5] - 2026-07-27

- Regenerated provider MCP configs with Plugin Forge 0.2.4 so cached installs launch from their own project root.
- Added regression coverage preventing host-directory editable installs in MCP launch arguments.

## [0.1.4] - 2026-07-27

- Fixed Codex and Claude MCP startup when launching `python -m usage_pulse.mcp_server`.
- Added module-entrypoint regression coverage.
- Made all hook wrappers self-bootstrap bundled source when provider runtimes invoke them directly.

## [0.1.3] - 2026-07-13

- Removed duplicate Claude hook declaration and rely on standard `hooks/hooks.json` autodiscovery.

## [0.1.2] - 2026-07-13

- Declared bundled Claude hooks in plugin metadata.
- Removed editable-install flags from generated MCP launch commands so cached installs remain portable.

## [0.1.1] - 2026-07-12

- Preserved provider identity, matchers, and status messages in Forge-generated hooks.
- Added marketplace artwork metadata for Codex install surfaces.
- Closed test SQLite connections and enforced warning-free regression tests.

## 0.1.0 - 2026-07-03

- Initial release.
- Added local SQLite telemetry storage, fail-open provider hooks, MCP query tools, `/pulse`, installer, and uninstaller.
