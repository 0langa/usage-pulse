from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from pytest import MonkeyPatch

from usage_pulse.db import PulseDB, TimeWindow, merge_unpaired_tool_calls
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


def test_hooks_pair_tool_calls_from_real_provider_payloads(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Claude Code and Codex payloads carry tool_use_id and tool_response, and no timestamp.
    monkeypatch.setenv("USAGE_PULSE_HOME", str(tmp_path))
    common = {
        "session_id": "abc123",
        "transcript_path": str(tmp_path / "t.jsonl"),
        "cwd": str(tmp_path),
        "permission_mode": "default",
        "tool_name": "Bash",
        "tool_input": {"command": "echo hello"},
        "tool_use_id": "toolu_01ABC123",
    }
    response = {"stdout": "hello", "stderr": "", "interrupted": False}
    handle_event("PreToolUse", json.dumps({**common, "hook_event_name": "PreToolUse"}), "claude")
    handle_event(
        "PostToolUse",
        json.dumps({**common, "hook_event_name": "PostToolUse", "tool_response": response}),
        "claude",
    )

    with closing(sqlite3.connect(tmp_path / "pulse.db")) as conn:
        rows = conn.execute(
            "SELECT id, completed_at, success, output_bytes FROM tool_calls"
        ).fetchall()
    assert len(rows) == 1
    call_id, completed_at, success, output_bytes = rows[0]
    assert call_id == "toolu_01ABC123"
    assert completed_at is not None
    assert success == 1
    assert output_bytes == len(json.dumps(response).encode("utf-8"))


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


def tool_rows(db_path: Path) -> list[tuple[str, str, str | None, int, int]]:
    with closing(sqlite3.connect(db_path)) as conn:
        return conn.execute(
            "SELECT id, timestamp, completed_at, duration_ms, input_bytes FROM tool_calls "
            "ORDER BY timestamp, id"
        ).fetchall()


def session_tool_totals(db_path: Path) -> tuple[int, int]:
    with closing(sqlite3.connect(db_path)) as conn:
        row = conn.execute("SELECT tool_call_count, tool_duration_ms FROM sessions").fetchone()
    return row[0], row[1]


def test_post_tool_use_prefers_the_duration_the_host_reports(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Claude Code's duration_ms is the tool's own run time. The time between
    # the hook events also holds the PreToolUse hook's run, startup included.
    monkeypatch.setenv("USAGE_PULSE_HOME", str(tmp_path))
    common = {"session_id": "s1", "cwd": str(tmp_path), "tool_name": "Bash"}
    handle_event(
        "PreToolUse",
        json.dumps({**common, "tool_use_id": "toolu_1", "timestamp": "2026-07-03T10:00:00Z"}),
        "claude",
    )
    handle_event(
        "PostToolUse",
        json.dumps(
            {**common, "tool_use_id": "toolu_1", "timestamp": "2026-07-03T10:00:05Z", "duration_ms": 12}
        ),
        "claude",
    )
    # A failure, and a completion whose PreToolUse never arrived.
    handle_event(
        "PostToolUseFailure",
        json.dumps({**common, "tool_use_id": "toolu_2", "error": "Exit code 1", "duration_ms": 40}),
        "claude",
    )

    durations = {row[0]: row[3] for row in tool_rows(tmp_path / "pulse.db")}
    assert durations == {"toolu_1": 12, "toolu_2": 40}
    assert session_tool_totals(tmp_path / "pulse.db") == (2, 52)


def test_hook_to_hook_durations_use_host_timestamps_in_any_format(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("USAGE_PULSE_HOME", str(tmp_path))
    common = {"session_id": "s1", "cwd": str(tmp_path), "tool_name": "Read"}
    stamps = [
        ("call-iso", "2026-07-03T10:00:00Z", "2026-07-03T10:00:01.500000+00:00"),
        ("call-ms", 1_783_072_800_000, 1_783_072_802_250),
        ("call-s", 1_783_072_900, 1_783_072_903.5),
    ]
    for call_id, started, finished in stamps:
        handle_event(
            "PreToolUse", json.dumps({**common, "tool_call_id": call_id, "timestamp": started}), "codex"
        )
        handle_event(
            "PostToolUse", json.dumps({**common, "tool_call_id": call_id, "timestamp": finished}), "codex"
        )

    rows = {row[0]: row for row in tool_rows(tmp_path / "pulse.db")}
    assert {call_id: rows[call_id][3] for call_id, _, _ in stamps} == {
        "call-iso": 1500,
        "call-ms": 2250,
        "call-s": 3500,
    }
    assert rows["call-iso"][1] == "2026-07-03T10:00:00+00:00"
    assert rows["call-ms"][1] == "2026-07-03T10:00:00+00:00"


def test_migrate_merges_tool_calls_recorded_twice_before_pairing(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Before 0.1.10 every call got a fallback id per event, so one call left an
    # open "started" row and a completed row that starts when it completes.
    monkeypatch.setenv("USAGE_PULSE_HOME", str(tmp_path))
    db_path = tmp_path / "pulse.db"
    common = {"session_id": "old", "cwd": str(tmp_path), "tool_name": "Bash"}

    def event(name: str, stamp: str, **extra: object) -> None:
        handle_event(name, json.dumps({**common, "timestamp": stamp, **extra}), "claude")

    event("PreToolUse", "2026-07-01T10:00:00+00:00", tool_input={"command": "echo one"})
    event("PostToolUse", "2026-07-01T10:00:02+00:00", tool_response="one")
    # A call whose PostToolUse never came (Claude sends PostToolUseFailure).
    event("PreToolUse", "2026-07-01T10:01:00+00:00", tool_input={"command": "false"})
    event("PreToolUse", "2026-07-01T10:02:00+00:00", tool_input={"command": "echo two"})
    event("PostToolUse", "2026-07-01T10:02:03+00:00", tool_response="two")
    # Paired by id since 0.1.10; never touched.
    event("PreToolUse", "2026-07-01T10:03:00+00:00", tool_use_id="toolu_9")
    event("PostToolUse", "2026-07-01T10:03:04+00:00", tool_use_id="toolu_9")
    # Still running when the repair runs.
    event("PreToolUse", "2026-07-01T10:04:00+00:00", tool_input={"command": "sleep 9"})
    assert len(tool_rows(db_path)) == 7
    totals = session_tool_totals(db_path)

    # The repair already ran (on an empty database) at the first event above;
    # take it back so the next migrate meets these rows as an upgrade would.
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute("DELETE FROM schema_migrations WHERE version LIKE 'repair_%'")
    PulseDB(db_path).migrate()

    rows = tool_rows(db_path)
    started = [row[1] for row in rows]
    assert started == [
        "2026-07-01T10:00:00+00:00",
        "2026-07-01T10:01:00+00:00",
        "2026-07-01T10:02:00+00:00",
        "2026-07-01T10:03:00+00:00",
        "2026-07-01T10:04:00+00:00",
    ]
    by_start = {row[1]: row for row in rows}
    one = by_start["2026-07-01T10:00:00+00:00"]
    assert one[2] == "2026-07-01T10:00:02+00:00"
    assert one[4] == len(json.dumps({"command": "echo one"}).encode("utf-8"))
    assert by_start["2026-07-01T10:01:00+00:00"][2] is None
    assert by_start["2026-07-01T10:02:00+00:00"][2] == "2026-07-01T10:02:03+00:00"
    assert by_start["2026-07-01T10:03:00+00:00"][0] == "toolu_9"
    assert by_start["2026-07-01T10:04:00+00:00"][2] is None
    assert session_tool_totals(db_path) == totals

    # Recorded once, and harmless if it ever runs again.
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.row_factory = sqlite3.Row
        merge_unpaired_tool_calls(conn)
    assert tool_rows(db_path) == rows
    with closing(sqlite3.connect(db_path)) as conn:
        versions = [row[0] for row in conn.execute("SELECT version FROM schema_migrations")]
    assert versions.count("repair_001_merge_unpaired_tool_calls") == 1
