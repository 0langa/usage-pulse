# Changelog

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
