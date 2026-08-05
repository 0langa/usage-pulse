from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from usage_pulse import __version__


def test_runtime_version_matches_project_forge_spec_and_plugin_manifests() -> None:
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    forge_text = (root / "forge.yaml").read_text(encoding="utf-8")
    forge_version = re.search(r"^version:\s*(\S+)$", forge_text, re.MULTILINE)
    manifests = [
        root / "plugin.json",
        root / ".claude-plugin" / "plugin.json",
        root / ".codex-plugin" / "plugin.json",
        root / "kimi.plugin.json",
    ]

    expected = project["project"]["version"]
    assert __version__ == expected
    assert forge_version is not None
    assert forge_version.group(1) == expected
    assert all(json.loads(path.read_text(encoding="utf-8"))["version"] == expected for path in manifests)
