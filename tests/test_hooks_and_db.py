from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from pytest import MonkeyPatch

from usage_pulse.db import PulseDB, TimeWindow
from usage_pulse.hooks import handle_event


def test_hooks_record_session_prompt_tool_and_summary(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("USAGE_PULSE_HOME", str(tmp_path))
    session_payload = {
        "session_id": "abc",
        "cwd": str(tmp_path),
        "model": "test-model",
        "timestamp": "2026-07-03T10:00:00+00:00",
    }
    handle_event("SessionStart", json.dumps(session_payload), "codex")
    handle_event(
        "UserPromptSubmit",
        json.dumps({**session_payload, "prompt": "hello world"}),
        "codex",
    )
    handle_event(
        "PreToolUse",
        json.dumps(
            {
                **session_payload,
                "timestamp": "2026-07-03T10:00:01+00:00",
                "tool_name": "Read",
                "tool_call_id": "call-1",
                "tool_input": {"file_path": str(tmp_path / "a.py")},
            }
        ),
        "codex",
    )
    handle_event(
        "PostToolUse",
        json.dumps(
            {
                **session_payload,
                "timestamp": "2026-07-03T10:00:03+00:00",
                "tool_name": "Read",
                "tool_call_id": "call-1",
                "tool_output": "content",
            }
        ),
        "codex",
    )
    summary = handle_event(
        "Stop",
        json.dumps({**session_payload, "timestamp": "2026-07-03T10:00:04+00:00"}),
        "codex",
    )

    assert summary is not None
    assert "usage-pulse:" in summary
    with closing(sqlite3.connect(tmp_path / "pulse.db")) as conn:
        row = conn.execute(
            "SELECT prompt_count, tool_call_count, file_read_count, hook_fire_count FROM sessions"
        ).fetchone()
    assert row == (1, 1, 1, 5)


def test_db_aggregates_top_compare_export_and_wipe(tmp_path: Path) -> None:
    db = PulseDB(tmp_path / "pulse.db")
    sid = "00000000-0000-0000-0000-000000000001"
    db.open_session(
        session_id=sid,
        provider="claude",
        model_id="sonnet",
        cwd=str(tmp_path),
        git_branch="main",
        host_session_id="host",
        timestamp="2026-07-03T10:00:00+00:00",
    )
    db.record_prompt(
        session_id=sid,
        timestamp="2026-07-03T10:00:01+00:00",
        input_hash="abc",
        char_count=12,
        token_estimate=3,
        privacy_sensitive=True,
    )
    db.start_tool_call(
        call_id="call",
        session_id=sid,
        provider="claude",
        name="Bash",
        input_bytes=10,
        timestamp="2026-07-03T10:00:02+00:00",
    )
    db.finish_tool_call(
        call_id="call",
        session_id=sid,
        provider="claude",
        name="Bash",
        success=True,
        output_bytes=20,
        error=None,
        timestamp="2026-07-03T10:00:04+00:00",
    )

    window = TimeWindow(
        start=datetime.fromisoformat("2026-07-03T00:00:00+00:00"),
        end=datetime.fromisoformat("2026-07-04T00:00:00+00:00"),
    )
    report = db.aggregate(window=window, group_by="provider")
    assert report["totals"]["sessions"] == 1
    assert db.top(by="tool", window=window, limit=10)["items"][0]["key"] == "Bash"
    exported = db.export(
        export_format="json",
        destination=tmp_path / "out.json",
        window=window,
    )
    assert Path(exported["path"]).exists()
    assert db.wipe()["wiped"] is True
