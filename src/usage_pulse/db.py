"""SQLite storage for Usage Pulse."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from usage_pulse.config import paths

JsonObject = dict[str, Any]


@dataclass(frozen=True)
class TimeWindow:
    start: datetime
    end: datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(dt: datetime | None = None) -> str:
    return (dt or utc_now()).astimezone(UTC).isoformat()


def parse_time(value: str | None) -> datetime:
    if not value:
        return utc_now()
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def window_from_range(start: str | None, end: str | None) -> TimeWindow:
    now = utc_now()
    return TimeWindow(
        parse_time(start) if start else now.replace(hour=0, minute=0, second=0, microsecond=0),
        parse_time(end) if end else now,
    )


def window_from_duration(duration: str) -> TimeWindow:
    now = utc_now()
    unit = duration[-1:]
    try:
        count = int(duration[:-1])
    except ValueError:
        count = 7
        unit = "d"
    delta = timedelta(days=count)
    if unit == "h":
        delta = timedelta(hours=count)
    elif unit == "w":
        delta = timedelta(weeks=count)
    return TimeWindow(now - delta, now)


def new_session_id(provider: str, host_session_id: str | None = None) -> str:
    if host_session_id:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"usage-pulse:{provider}:{host_session_id}"))
    return str(uuid.uuid4())


class PulseDB:
    def __init__(self, db_path: Path | None = None, migrations_dir: Path | None = None) -> None:
        self.db_path = db_path or paths().db_path
        self.migrations_dir = migrations_dir or Path(__file__).resolve().parents[2] / "migrations"

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def migrate(self) -> None:
        with self.connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            applied = {
                row["version"]
                for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
            }
            for path in sorted(self.migrations_dir.glob("*.sql")):
                version = path.stem
                if version in applied:
                    continue
                conn.executescript(path.read_text(encoding="utf-8"))
                conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, iso()),
                )

    def open_session(
        self,
        *,
        session_id: str,
        provider: str,
        model_id: str | None,
        cwd: str | None,
        git_branch: str | None,
        host_session_id: str | None,
        timestamp: str | None = None,
    ) -> None:
        self.migrate()
        now = timestamp or iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions(id, host_session_id, provider, model_id, cwd, git_branch,
                  started_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  model_id=COALESCE(excluded.model_id, sessions.model_id),
                  cwd=COALESCE(excluded.cwd, sessions.cwd),
                  git_branch=COALESCE(excluded.git_branch, sessions.git_branch),
                  updated_at=excluded.updated_at
                """,
                (session_id, host_session_id, provider, model_id, cwd, git_branch, now, now),
            )

    def close_session(self, session_id: str, timestamp: str | None = None) -> JsonObject:
        now = timestamp or iso()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT started_at FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            duration_ms = 0
            if row:
                duration_ms = max(
                    0,
                    int(
                        (parse_time(now) - parse_time(str(row["started_at"]))).total_seconds()
                        * 1000
                    ),
                )
            conn.execute(
                "UPDATE sessions SET ended_at = ?, duration_ms = ?, updated_at = ? WHERE id = ?",
                (now, duration_ms, now, session_id),
            )
        return self.session(session_id)

    def record_hook_fire(
        self,
        *,
        session_id: str,
        provider: str,
        event: str,
        payload_bytes: int,
        success: bool = True,
        error: str | None = None,
        timestamp: str | None = None,
    ) -> None:
        self._execute_event(
            """
            INSERT INTO hook_fires(session_id, timestamp, provider, event, payload_bytes, success, error)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, timestamp or iso(), provider, event, payload_bytes, int(success), error),
        )
        self._bump(session_id, hook_fire_count=1)

    def record_prompt(
        self,
        *,
        session_id: str,
        timestamp: str,
        input_hash: str,
        char_count: int,
        token_estimate: int,
        privacy_sensitive: bool,
    ) -> None:
        self._execute_event(
            """
            INSERT INTO prompts(session_id, timestamp, input_hash, char_count, token_estimate,
              privacy_sensitive)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, timestamp, input_hash, char_count, token_estimate, int(privacy_sensitive)),
        )
        self._bump(session_id, prompt_count=1, input_tokens_est=token_estimate)

    def start_tool_call(
        self,
        *,
        call_id: str,
        session_id: str,
        provider: str,
        name: str,
        input_bytes: int,
        timestamp: str,
    ) -> None:
        self._execute_event(
            """
            INSERT INTO tool_calls(id, session_id, timestamp, provider, name, input_bytes)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET input_bytes=excluded.input_bytes
            """,
            (call_id, session_id, timestamp, provider, name, input_bytes),
        )

    def finish_tool_call(
        self,
        *,
        call_id: str,
        session_id: str,
        provider: str,
        name: str,
        success: bool,
        output_bytes: int,
        error: str | None,
        timestamp: str,
    ) -> None:
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT timestamp FROM tool_calls WHERE id = ?", (call_id,)
            ).fetchone()
            if existing is None:
                started = timestamp
                duration_ms = 0
                conn.execute(
                    """
                    INSERT INTO tool_calls(id, session_id, timestamp, provider, name)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (call_id, session_id, started, provider, name),
                )
            else:
                started = str(existing["timestamp"])
                duration_ms = max(
                    0, int((parse_time(timestamp) - parse_time(started)).total_seconds() * 1000)
                )
            conn.execute(
                """
                UPDATE tool_calls
                SET completed_at=?, duration_ms=?, success=?, output_bytes=?, error=?
                WHERE id=?
                """,
                (timestamp, duration_ms, int(success), output_bytes, error, call_id),
            )
        self._bump(
            session_id,
            tool_call_count=1,
            tool_success_count=1 if success else 0,
            tool_failure_count=0 if success else 1,
            tool_duration_ms=duration_ms,
            tool_output_bytes=output_bytes,
        )

    def record_file_op(
        self,
        *,
        session_id: str,
        operation: str,
        path: str,
        timestamp: str,
    ) -> None:
        self._execute_event(
            "INSERT INTO file_ops(session_id, timestamp, operation, path) VALUES (?, ?, ?, ?)",
            (session_id, timestamp, operation, path),
        )
        counts = {
            "read": {"file_read_count": 1},
            "edit": {"file_edit_count": 1},
            "write": {"file_write_count": 1},
        }.get(operation, {})
        self._bump(session_id, **counts)
        self._refresh_unique_paths(session_id)

    def record_mcp_call(
        self,
        *,
        session_id: str,
        provider: str,
        server: str,
        tool: str,
        duration_ms: int,
        success: bool,
        timestamp: str,
    ) -> None:
        self._execute_event(
            """
            INSERT INTO mcp_calls(session_id, timestamp, provider, server, tool, duration_ms, success)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, timestamp, provider, server, tool, duration_ms, int(success)),
        )
        self._bump(session_id, mcp_call_count=1)

    def record_web_search(
        self,
        *,
        session_id: str,
        timestamp: str,
        query_hash: str,
        result_count: int | None,
    ) -> None:
        self._execute_event(
            """
            INSERT INTO web_searches(session_id, timestamp, query_hash, result_count)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, timestamp, query_hash, result_count),
        )
        self._bump(session_id, web_search_count=1)

    def record_subagent(self, *, session_id: str, timestamp: str, name: str) -> None:
        self._execute_event(
            "INSERT INTO subagents(session_id, timestamp, name) VALUES (?, ?, ?)",
            (session_id, timestamp, name),
        )
        self._bump(session_id, subagent_count=1)

    def record_compaction(
        self,
        *,
        session_id: str,
        timestamp: str,
        trigger: str | None,
        token_count: int | None,
    ) -> None:
        self._execute_event(
            """
            INSERT INTO compactions(session_id, timestamp, trigger, token_count)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, timestamp, trigger, token_count),
        )
        self._bump(session_id, compaction_count=1)

    def today(self) -> JsonObject:
        now = utc_now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return self.aggregate(TimeWindow(start, now), group_by="session")

    def session(self, session_id: str) -> JsonObject:
        self.migrate()
        with self.connect() as conn:
            if session_id == "current":
                row = conn.execute(
                    "SELECT id FROM sessions ORDER BY updated_at DESC LIMIT 1"
                ).fetchone()
                session_id = str(row["id"]) if row else ""
            session_row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if session_row is None:
                return {"summary": "No session found.", "session": None}
            detail = dict(session_row)
            detail["unique_paths"] = json.loads(str(detail.pop("unique_paths_json") or "[]"))
            detail["tools"] = self._rows(
                conn,
                "SELECT name, count(*) AS count, sum(duration_ms) AS duration_ms, "
                "sum(output_bytes) AS output_bytes FROM tool_calls WHERE session_id=? GROUP BY name",
                (session_id,),
            )
            detail["mcp"] = self._rows(
                conn,
                "SELECT server, tool, count(*) AS count, sum(duration_ms) AS duration_ms "
                "FROM mcp_calls WHERE session_id=? GROUP BY server, tool",
                (session_id,),
            )
            detail["file_ops"] = self._rows(
                conn,
                "SELECT operation, count(*) AS count FROM file_ops WHERE session_id=? GROUP BY operation",
                (session_id,),
            )
            detail["web_searches"] = self._rows(
                conn,
                "SELECT query_hash, result_count, timestamp FROM web_searches WHERE session_id=? "
                "ORDER BY timestamp",
                (session_id,),
            )
        return {"summary": self._session_summary(detail), "session": detail}

    def aggregate(self, window: TimeWindow, group_by: str) -> JsonObject:
        self.migrate()
        start = window.start.isoformat()
        end = window.end.isoformat()
        group_expr = {
            "day": "substr(started_at, 1, 10)",
            "provider": "provider",
            "project": "cwd",
            "session": "id",
        }.get(group_by, "id")
        with self.connect() as conn:
            totals = self._one(
                conn,
                """
                SELECT count(*) AS sessions, coalesce(sum(prompt_count),0) AS prompts,
                  coalesce(sum(input_tokens_est),0) AS input_tokens_est,
                  coalesce(sum(tool_call_count),0) AS tool_calls,
                  coalesce(sum(tool_duration_ms),0) AS tool_duration_ms,
                  coalesce(sum(web_search_count),0) AS web_searches,
                  coalesce(sum(file_read_count),0) AS file_reads,
                  coalesce(sum(file_edit_count),0) AS file_edits,
                  coalesce(sum(file_write_count),0) AS file_writes,
                  coalesce(sum(mcp_call_count),0) AS mcp_calls,
                  coalesce(sum(subagent_count),0) AS subagents,
                  coalesce(sum(compaction_count),0) AS compactions
                FROM sessions WHERE started_at >= ? AND started_at <= ?
                """,
                (start, end),
            )
            groups = self._rows(
                conn,
                f"""
                SELECT {group_expr} AS key, provider, count(*) AS sessions,
                  coalesce(sum(prompt_count),0) AS prompts,
                  coalesce(sum(input_tokens_est),0) AS input_tokens_est,
                  coalesce(sum(tool_call_count),0) AS tool_calls,
                  coalesce(sum(duration_ms),0) AS duration_ms
                FROM sessions WHERE started_at >= ? AND started_at <= ?
                GROUP BY key, provider ORDER BY key
                """,
                (start, end),
            )
        summary = (
            f"{totals['sessions']} sessions, {totals['prompts']} prompts, "
            f"{totals['tool_calls']} tool calls, {totals['input_tokens_est']} est. input tokens."
        )
        return {"summary": summary, "from": start, "to": end, "totals": totals, "groups": groups}

    def top(self, *, by: str, window: TimeWindow, limit: int) -> JsonObject:
        start = window.start.isoformat()
        end = window.end.isoformat()
        queries = {
            "tool": (
                "SELECT name AS key, count(*) AS count, coalesce(sum(duration_ms),0) AS duration_ms "
                "FROM tool_calls WHERE timestamp >= ? AND timestamp <= ? GROUP BY name "
                "ORDER BY count DESC LIMIT ?"
            ),
            "mcp": (
                "SELECT server || '.' || tool AS key, count(*) AS count, "
                "coalesce(sum(duration_ms),0) AS duration_ms FROM mcp_calls "
                "WHERE timestamp >= ? AND timestamp <= ? GROUP BY key ORDER BY count DESC LIMIT ?"
            ),
            "agent": (
                "SELECT name AS key, count(*) AS count, 0 AS duration_ms FROM subagents "
                "WHERE timestamp >= ? AND timestamp <= ? GROUP BY name ORDER BY count DESC LIMIT ?"
            ),
            "project": (
                "SELECT cwd AS key, count(*) AS count, coalesce(sum(duration_ms),0) AS duration_ms "
                "FROM sessions WHERE started_at >= ? AND started_at <= ? GROUP BY cwd "
                "ORDER BY count DESC LIMIT ?"
            ),
        }
        with self.connect() as conn:
            rows = self._rows(conn, queries.get(by, queries["tool"]), (start, end, limit))
        return {"summary": f"Top {by} entries for window.", "by": by, "items": rows}

    def compare(self, window: TimeWindow) -> JsonObject:
        span = window.end - window.start
        prior = TimeWindow(window.start - span, window.start)
        current = self.aggregate(window, "provider")["totals"]
        previous = self.aggregate(prior, "provider")["totals"]
        delta = {
            key: int(current.get(key, 0)) - int(previous.get(key, 0))
            for key in current
            if isinstance(current.get(key), int)
        }
        return {
            "summary": "Current window compared with prior window.",
            "current": current,
            "prior": previous,
            "delta": delta,
            "from": window.start.isoformat(),
            "to": window.end.isoformat(),
            "prior_from": prior.start.isoformat(),
            "prior_to": prior.end.isoformat(),
        }

    def export(self, *, export_format: str, destination: Path, window: TimeWindow) -> JsonObject:
        data = self.aggregate(window, "session")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if export_format == "csv":
            lines = ["key,provider,sessions,prompts,input_tokens_est,tool_calls,duration_ms"]
            for row in data["groups"]:
                lines.append(
                    ",".join(
                        str(row.get(field, ""))
                        for field in [
                            "key",
                            "provider",
                            "sessions",
                            "prompts",
                            "input_tokens_est",
                            "tool_calls",
                            "duration_ms",
                        ]
                    )
                )
            destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            destination.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return {"summary": f"Exported usage data to {destination}.", "path": str(destination)}

    def wipe(self) -> JsonObject:
        with self.connect() as conn:
            for table in [
                "web_searches",
                "subagents",
                "compactions",
                "mcp_calls",
                "file_ops",
                "hook_fires",
                "tool_calls",
                "prompts",
                "sessions",
            ]:
                conn.execute(f"DELETE FROM {table}")
        return {"summary": "Usage Pulse database wiped.", "wiped": True}

    def _execute_event(self, sql: str, params: Sequence[Any]) -> None:
        with self.connect() as conn:
            conn.execute(sql, params)

    def _bump(self, session_id: str, **counts: int) -> None:
        if not counts:
            return
        assignments = ", ".join(f"{key} = {key} + ?" for key in counts)
        values: list[Any] = list(counts.values())
        values.extend([iso(), session_id])
        with self.connect() as conn:
            conn.execute(
                f"UPDATE sessions SET {assignments}, updated_at = ? WHERE id = ?",
                values,
            )

    def _refresh_unique_paths(self, session_id: str) -> None:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT path FROM file_ops WHERE session_id = ? ORDER BY path",
                (session_id,),
            ).fetchall()
            conn.execute(
                "UPDATE sessions SET unique_paths_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps([str(row["path"]) for row in rows]), iso(), session_id),
            )

    @staticmethod
    def _rows(conn: sqlite3.Connection, sql: str, params: Iterable[Any]) -> list[JsonObject]:
        return [dict(row) for row in conn.execute(sql, tuple(params)).fetchall()]

    @staticmethod
    def _one(conn: sqlite3.Connection, sql: str, params: Iterable[Any]) -> JsonObject:
        row = conn.execute(sql, tuple(params)).fetchone()
        return dict(row) if row else {}

    @staticmethod
    def _session_summary(detail: JsonObject) -> str:
        return (
            f"{detail['provider']} session {detail['id']}: {detail['prompt_count']} prompts, "
            f"{detail['tool_call_count']} tool calls, {detail['input_tokens_est']} est. input tokens."
        )
