# Usage Pulse — Status & Roadmap
_Portfolio audit: 2026-07-11_

## What this is

Local, passive, privacy-preserving usage telemetry for Claude Code, Codex, and Kimi Code:
provider hooks write per-session counters (prompts, tool calls, file ops, MCP calls, web
searches, compactions) into `~/.usage-pulse/pulse.db`, and a bundled MCP server answers
questions about them. Stack: Python 3.11+ with `mcp`, `pydantic`, and `tiktoken`; SQLite with a
versioned migration (`migrations/001_init.sql`); `uv` + hatchling packaging; ruff, strict mypy,
and pytest with an enforced 80% coverage floor; and a `forge.yaml` so the plugin is managed by
plugin-forge.

## Current state

This is the most finished of the four portfolio projects — **v0.1.6 is tagged and released**
(CHANGELOG dated 2026-07-27). The package metadata, Forge spec, runtime package, legacy
`plugin.json`, and active provider manifests agree on 0.1.6.

What works:

- Core logic in `src/usage_pulse/`: `db.py` (573 lines — schema plus all aggregation queries),
  `hooks.py` (321 lines, fail-open event ingestion), and `mcp_server.py` exposing seven tools
  (`pulse.today`, `pulse.session`, `pulse.range`, `pulse.top`, `pulse.compare`, `pulse.export`,
  `pulse.wipe`), plus `config.py`, `tokens.py`, and `kimi_tool.py`.
- Hook wiring ships in-plugin: `hooks/hooks.json` (with Windows-specific `commandWindows`
  variants) and `hooks/codex-hooks.json`, backed by thin event scripts in `hooks/`.
- `scripts/install.py --provider all` and `scripts/uninstall.py` handle per-provider install
  with registry backups and an install receipt at `~/.usage-pulse/install-receipt.json`.
- Two skills (`skills/usage-report`, `skills/using-pulse`) and the `/pulse` command provide the
  chat surface; the plugin is demonstrably installed and functioning in the live environment.
- Privacy design is solid: prompt bodies are never stored (length, SHA-256 hash, and a token
  estimate only) and the plugin makes no network calls.

Gaps and loose ends:

- `hooks/session_end.py` is a legacy wrapper used by the legacy Kimi installer helper, while the
  generated provider manifests use `Stop`. Decide whether to retain that legacy path or remove it
  together with the unused helper.
- Test coverage is real but thin for the surface area: three files totaling 285 lines
  (`tests/test_hooks_and_db.py`, `test_install.py`, `test_mcp_server.py`) against roughly
  1,080 lines of source.
- The CI workflow defines Ruff, mypy, and pytest gates on Windows and Linux; a remote first run
  is still required after publishing the source changes.

## Definition of "finished"

v1.0 means: every script in `hooks/` is wired in both provider hook manifests or removed; a
GitHub Actions workflow runs ruff, strict mypy, and pytest (with the 80% coverage gate) on
Windows and Linux and is green; install → record → report → uninstall has been verified
end-to-end on all three providers with the receipt confirming clean rollback; the seven MCP
tools have tests for empty-database and bad-argument paths; and `CHANGELOG.md` plus a `v1.0.0`
tag ship the result through the plugin-forge release flow.

## Roadmap

### Phase 1 — Now (next 1-2 weeks)

- Decide the fate of the legacy Kimi `SessionEnd` helper: retain and test that separate installer
  path, or remove the helper and `hooks/session_end.py` once no supported installer uses it.
- Extend `tests/test_mcp_server.py` with empty-database, invalid-range, and
  `pulse.wipe`-without-confirm cases.

### Phase 2 — Next (2-6 weeks)

- Run the full install/uninstall verification matrix on Claude Code, Codex, and Kimi Code, fix
  any receipt or registry drift found, then cut v0.2.0 via the plugin-forge release skill.
- Enrich reporting where the data already exists in `db.py`: per-project and per-branch rollups
  in `/pulse` and the `usage-report` skill, and a `group_by=model` option for `pulse.range`.
- Document the SQLite schema (tables and retention expectations) in the README so `pulse.export`
  output is usable outside the plugin.

### Phase 3 — Later (optional/stretch)

- A retention/pruning policy (for example, auto-compacting rows older than N days) alongside
  `pulse.wipe`.
- A small local HTML dashboard generated from `pulse.export` output.
- Optional calibration of token estimates against provider-reported usage where available.

## Effort to "finished"

**S (under one week of part-time work).** The product is already released, version-consistent,
and in daily use; what stands between 0.1.6 and a credible 1.0 is CI, legacy installer cleanup, a
modest test top-up, and a three-provider verification pass.
