from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from pytest import MonkeyPatch

from usage_pulse.db import iso
from usage_pulse.hooks import handle_event
from usage_pulse.mcp_server import (
    pulse_compare,
    pulse_export,
    pulse_range,
    pulse_session,
    pulse_today,
    pulse_top,
    pulse_wipe,
)


def test_module_entrypoint_starts_mcp(monkeypatch: MonkeyPatch) -> None:
    started = False

    def fake_run(self: FastMCP) -> None:
        nonlocal started
        started = True

    monkeypatch.setattr(FastMCP, "run", fake_run)
    monkeypatch.delitem(sys.modules, "usage_pulse.mcp_server", raising=False)
    runpy.run_module("usage_pulse.mcp_server", run_name="__main__")

    assert started is True


def test_mcp_tools_return_structured_json(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("USAGE_PULSE_HOME", str(tmp_path))
    payload = {
        "session_id": "mcp",
        "cwd": str(tmp_path),
        "timestamp": iso(),
    }
    handle_event("SessionStart", json.dumps(payload), "kimi")
    handle_event("UserPromptSubmit", json.dumps({**payload, "prompt": "hi"}), "kimi")
    handle_event(
        "PostToolUse",
        json.dumps(
            {
                **payload,
                "tool_name": "mcp__server__tool",
                "tool_call_id": "mcp-call",
                "tool_output": {"ok": True},
            }
        ),
        "kimi",
    )
    handle_event(
        "PostToolUse",
        json.dumps(
            {
                **payload,
                "tool_name": "WebSearch",
                "tool_call_id": "web-call",
                "tool_input": {"query": "private query"},
                "tool_output": [{"title": "x"}],
            }
        ),
        "kimi",
    )
    handle_event(
        "PostToolUse",
        json.dumps(
            {
                **payload,
                "tool_name": "Task",
                "tool_call_id": "task-call",
                "tool_input": {"subagent_type": "reviewer"},
            }
        ),
        "kimi",
    )
    handle_event("PreCompact", json.dumps({**payload, "trigger": "manual"}), "kimi")

    today = pulse_today()
    assert "summary" in today
    assert today["totals"]["sessions"] >= 1
    assert pulse_session("current")["session"]["provider"] == "kimi"
    assert pulse_top(by="tool", limit=5, window="7d")["by"] == "tool"
    assert pulse_top(by="mcp", limit=5, window="7d")["items"][0]["key"] == "server.tool"
    assert pulse_top(by="agent", limit=5, window="7d")["items"][0]["key"] == "reviewer"
    assert pulse_range(group_by="provider")["totals"]["prompts"] >= 1
    assert "delta" in pulse_compare(window="1d")
    assert Path(pulse_export(format="csv", to=str(tmp_path / "out.csv"))["path"]).exists()
    assert pulse_wipe(confirm=False)["wiped"] is False
