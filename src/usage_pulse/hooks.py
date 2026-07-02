"""Fail-open hook entrypoint for all supported providers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import traceback
import uuid
from typing import Any

from usage_pulse.config import provider_from_env
from usage_pulse.db import PulseDB, iso, new_session_id
from usage_pulse.tokens import estimate_tokens

JsonObject = dict[str, Any]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("event")
    parser.add_argument("--provider", default=None)
    args = parser.parse_args()
    provider = (args.provider or provider_from_env()).lower()
    event = str(args.event)
    raw = sys.stdin.read()
    try:
        result = handle_event(event, raw, provider)
        if event.lower() in {"stop", "sessionend"} and result:
            print(result)
    except Exception as exc:
        log_error(event, exc)
    raise SystemExit(0)


def handle_event(event: str, raw_payload: str, provider: str) -> str | None:
    payload = parse_payload(raw_payload)
    db = PulseDB()
    db.migrate()
    timestamp = str(payload.get("timestamp") or iso())
    host_session_id = scalar(payload, "session_id", "transcript_path", "conversation_id")
    session_id = session_uuid(provider, host_session_id)
    cwd = scalar(payload, "cwd") or os.getcwd()
    model_id = scalar(payload, "model", "model_id", "modelId")
    branch = scalar(payload, "git_branch", "branch") or git_branch(cwd)
    db.open_session(
        session_id=session_id,
        provider=provider,
        model_id=model_id,
        cwd=cwd,
        git_branch=branch,
        host_session_id=host_session_id,
        timestamp=timestamp,
    )
    db.record_hook_fire(
        session_id=session_id,
        provider=provider,
        event=event,
        payload_bytes=len(raw_payload.encode("utf-8")),
        timestamp=timestamp,
    )
    normalized = normalize_event(event)
    if normalized == "userpromptsubmit":
        record_prompt(db, session_id, payload, timestamp, model_id)
    elif normalized == "pretooluse":
        record_pre_tool(db, session_id, provider, payload, timestamp)
    elif normalized in {"posttooluse", "posttoolusefailure"}:
        record_post_tool(db, session_id, provider, payload, timestamp, normalized)
    elif normalized == "precompact":
        db.record_compaction(
            session_id=session_id,
            timestamp=timestamp,
            trigger=scalar(payload, "trigger", "reason"),
            token_count=int_or_none(payload.get("token_count")),
        )
    elif normalized in {"subagentstart", "subagentstop"}:
        db.record_subagent(
            session_id=session_id,
            timestamp=timestamp,
            name=scalar(payload, "agent_name", "name") or "unknown",
        )
    elif normalized in {"stop", "sessionend"}:
        return compact_summary(db.close_session(session_id, timestamp))
    return None


def parse_payload(raw_payload: str) -> JsonObject:
    if not raw_payload.strip():
        return {}
    value = json.loads(raw_payload)
    return value if isinstance(value, dict) else {"value": value}


def normalize_event(event: str) -> str:
    return event.replace("_", "").replace("-", "").lower()


def session_uuid(provider: str, host_session_id: str | None) -> str:
    return new_session_id(provider, host_session_id or os.environ.get("USAGE_PULSE_SESSION_ID"))


def scalar(payload: JsonObject, *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def record_prompt(
    db: PulseDB, session_id: str, payload: JsonObject, timestamp: str, model_id: str | None
) -> None:
    prompt = scalar(payload, "prompt", "input", "text") or ""
    db.record_prompt(
        session_id=session_id,
        timestamp=timestamp,
        input_hash=sha(prompt),
        char_count=len(prompt),
        token_estimate=estimate_tokens(prompt, model_id),
        privacy_sensitive=True,
    )


def record_pre_tool(
    db: PulseDB, session_id: str, provider: str, payload: JsonObject, timestamp: str
) -> None:
    tool_name = tool_name_from_payload(payload)
    call_id = call_id_from_payload(payload, session_id, tool_name, timestamp)
    tool_input = payload.get("tool_input") or payload.get("input") or {}
    db.start_tool_call(
        call_id=call_id,
        session_id=session_id,
        provider=provider,
        name=tool_name,
        input_bytes=len(json.dumps(tool_input, default=str).encode("utf-8")),
        timestamp=timestamp,
    )
    for operation, path in file_ops_from_tool(tool_name, tool_input):
        db.record_file_op(
            session_id=session_id, operation=operation, path=path, timestamp=timestamp
        )


def record_post_tool(
    db: PulseDB,
    session_id: str,
    provider: str,
    payload: JsonObject,
    timestamp: str,
    normalized: str,
) -> None:
    tool_name = tool_name_from_payload(payload)
    call_id = call_id_from_payload(payload, session_id, tool_name, timestamp)
    output = payload.get("tool_output") or payload.get("output") or payload.get("result") or ""
    error = scalar(payload, "error", "error_message")
    success = normalized != "posttoolusefailure" and not error
    output_bytes = len(json.dumps(output, default=str).encode("utf-8"))
    db.finish_tool_call(
        call_id=call_id,
        session_id=session_id,
        provider=provider,
        name=tool_name,
        success=success,
        output_bytes=output_bytes,
        error=error,
        timestamp=timestamp,
    )
    maybe_record_web_search(db, session_id, tool_name, payload, timestamp)
    maybe_record_mcp(db, session_id, provider, tool_name, payload, timestamp, success)
    maybe_record_subagent(db, session_id, tool_name, payload, timestamp)


def tool_name_from_payload(payload: JsonObject) -> str:
    return scalar(payload, "tool_name", "name", "tool") or "unknown"


def call_id_from_payload(
    payload: JsonObject, session_id: str, tool_name: str, timestamp: str
) -> str:
    explicit = scalar(payload, "tool_call_id", "call_id", "id")
    if explicit:
        return explicit
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{session_id}:{tool_name}:{timestamp}"))


def file_ops_from_tool(tool_name: str, tool_input: Any) -> list[tuple[str, str]]:
    if not isinstance(tool_input, dict):
        return []
    lower = tool_name.lower()
    operation = None
    if any(marker in lower for marker in ["read", "grep", "glob", "ls"]):
        operation = "read"
    elif any(marker in lower for marker in ["edit", "strreplace", "patch"]):
        operation = "edit"
    elif any(marker in lower for marker in ["write", "create"]):
        operation = "write"
    if operation is None:
        return []
    paths: list[str] = []
    for key in ["file_path", "path", "filepath", "target_file"]:
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            paths.append(value)
    return [(operation, path) for path in sorted(set(paths))]


def maybe_record_web_search(
    db: PulseDB, session_id: str, tool_name: str, payload: JsonObject, timestamp: str
) -> None:
    lower = tool_name.lower()
    if "web" not in lower and "search" not in lower:
        return
    tool_input = payload.get("tool_input") or payload.get("input") or {}
    query = ""
    if isinstance(tool_input, dict):
        query = str(
            tool_input.get("query") or tool_input.get("q") or tool_input.get("search_query") or ""
        )
    output = payload.get("tool_output") or payload.get("output") or []
    result_count = len(output) if isinstance(output, list) else None
    db.record_web_search(
        session_id=session_id,
        timestamp=timestamp,
        query_hash=sha(query),
        result_count=result_count,
    )


def maybe_record_mcp(
    db: PulseDB,
    session_id: str,
    provider: str,
    tool_name: str,
    payload: JsonObject,
    timestamp: str,
    success: bool,
) -> None:
    server = scalar(payload, "mcp_server", "server")
    tool = scalar(payload, "mcp_tool", "tool")
    if not server and tool_name.startswith("mcp__"):
        parts = tool_name.split("__", 2)
        if len(parts) == 3:
            server = parts[1]
            tool = parts[2]
    if not server:
        return
    db.record_mcp_call(
        session_id=session_id,
        provider=provider,
        server=server,
        tool=tool or tool_name,
        duration_ms=int_or_none(payload.get("duration_ms")) or 0,
        success=success,
        timestamp=timestamp,
    )


def maybe_record_subagent(
    db: PulseDB, session_id: str, tool_name: str, payload: JsonObject, timestamp: str
) -> None:
    lower = tool_name.lower()
    if lower not in {"task", "subagent"} and "subagent" not in lower:
        return
    tool_input = payload.get("tool_input") or payload.get("input") or {}
    name = "unknown"
    if isinstance(tool_input, dict):
        raw = (
            tool_input.get("subagent_type")
            or tool_input.get("agent_name")
            or tool_input.get("name")
        )
        name = str(raw) if raw else name
    db.record_subagent(session_id=session_id, timestamp=timestamp, name=name)


def compact_summary(session_result: JsonObject) -> str:
    summary = str(session_result.get("summary") or "Usage Pulse session closed.")
    return f"usage-pulse: {summary}"


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def git_branch(cwd: str | None) -> str | None:
    if not cwd:
        return None
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return None
    branch = result.stdout.strip()
    return branch or None


def log_error(event: str, exc: Exception) -> None:
    from usage_pulse.config import paths

    pulse_paths = paths()
    pulse_paths.home.mkdir(parents=True, exist_ok=True)
    with pulse_paths.errors_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{iso()}] hook={event} error={exc}\n")
        handle.write(traceback.format_exc())
        handle.write("\n")
