"""MCP server exposing Usage Pulse reports."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from usage_pulse.db import PulseDB, window_from_duration, window_from_range

JsonObject = dict[str, Any]

mcp = FastMCP("usage-pulse")


@mcp.tool(name="pulse.today")
def pulse_today() -> JsonObject:
    """Return today's totals and per-session breakdown."""
    return PulseDB().today()


@mcp.tool(name="pulse.session")
def pulse_session(id: str = "current") -> JsonObject:
    """Return one detailed session record."""
    return PulseDB().session(id)


@mcp.tool(name="pulse.range")
def pulse_range(
    from_: Annotated[str | None, Field(alias="from")] = None,
    to: str | None = None,
    group_by: Literal["day", "provider", "project"] = "day",
) -> JsonObject:
    """Return aggregate usage for a time range."""
    return PulseDB().aggregate(window_from_range(from_, to), group_by)


@mcp.tool(name="pulse.top")
def pulse_top(
    by: Literal["tool", "mcp", "agent", "project"] = "tool",
    limit: int = 10,
    window: str = "7d",
) -> JsonObject:
    """Return leaderboards for a recent window."""
    return PulseDB().top(by=by, limit=limit, window=window_from_duration(window))


@mcp.tool(name="pulse.compare")
def pulse_compare(window: str = "7d") -> JsonObject:
    """Compare this window with the prior equivalent window."""
    return PulseDB().compare(window_from_duration(window))


@mcp.tool(name="pulse.export")
def pulse_export(
    format: Literal["json", "csv"] = "json",
    to: str = "usage-pulse-export.json",
    from_: Annotated[str | None, Field(alias="from")] = None,
    until: str | None = None,
) -> JsonObject:
    """Export usage data to JSON or CSV."""
    return PulseDB().export(
        export_format=format,
        destination=Path(to).expanduser(),
        window=window_from_range(from_, until),
    )


@mcp.tool(name="pulse.wipe")
def pulse_wipe(confirm: bool = False) -> JsonObject:
    """Delete local telemetry rows when confirm is true."""
    if not confirm:
        return {"summary": "Pass confirm=true to wipe Usage Pulse data.", "wiped": False}
    return PulseDB().wipe()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
