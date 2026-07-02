"""Paths and runtime configuration for Usage Pulse."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

APP_DIR_ENV = "USAGE_PULSE_HOME"
PROVIDER_ENV = "USAGE_PULSE_PROVIDER"
DEFAULT_PROVIDER = "unknown"


@dataclass(frozen=True)
class PulsePaths:
    home: Path
    db_path: Path
    errors_path: Path
    current_sessions_path: Path


def pulse_home() -> Path:
    raw = os.environ.get(APP_DIR_ENV)
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".usage-pulse"


def paths() -> PulsePaths:
    root = pulse_home()
    return PulsePaths(
        home=root,
        db_path=root / "pulse.db",
        errors_path=root / "errors.log",
        current_sessions_path=root / "current-sessions.json",
    )


def provider_from_env(default: str = DEFAULT_PROVIDER) -> str:
    return os.environ.get(PROVIDER_ENV, default).strip().lower() or default
