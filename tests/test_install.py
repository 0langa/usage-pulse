from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from pytest import MonkeyPatch


def load_script(name: str) -> Any:
    path = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_install_and_uninstall_against_temp_home(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    install = load_script("install")
    uninstall = load_script("uninstall")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("USAGE_PULSE_CLAUDE_SETTINGS", str(tmp_path / ".claude" / "settings.json"))
    monkeypatch.setenv("USAGE_PULSE_CODEX_CONFIG", str(tmp_path / ".codex" / "config.toml"))
    monkeypatch.setenv("USAGE_PULSE_KIMI_CONFIG", str(tmp_path / ".kimi" / "config.toml"))
    monkeypatch.setenv("KIMI_CODE_HOME", str(tmp_path / ".kimi-code"))
    monkeypatch.setenv(
        "USAGE_PULSE_CLAUDE_PLUGIN_DIR", str(tmp_path / ".claude" / "skills" / "usage-pulse")
    )
    monkeypatch.setenv("USAGE_PULSE_CODEX_PLUGIN_DIR", str(tmp_path / "plugins" / "usage-pulse"))
    monkeypatch.setenv(
        "USAGE_PULSE_KIMI_PLUGIN_DIR",
        str(tmp_path / ".kimi-code" / "plugins" / "managed" / "usage-pulse"),
    )
    source = Path(__file__).resolve().parents[1]

    for provider in ["claude", "codex", "kimi"]:
        receipt = install.Receipt(installed_at="now", source=str(source))
        install.install_provider(provider, source, receipt)
        receipt.save(tmp_path / ".usage-pulse" / "install-receipt.json")

    claude = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert "usage-pulse" in claude["mcpServers"]
    assert (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8").count(
        "usage-pulse"
    ) > 0
    assert not (tmp_path / ".kimi" / "config.toml").exists()

    installed = json.loads(
        (tmp_path / ".kimi-code" / "plugins" / "installed.json").read_text(encoding="utf-8")
    )
    entries = [p for p in installed["plugins"] if p.get("id") == "usage-pulse"]
    assert len(entries) == 1
    assert entries[0]["root"] == str(tmp_path / ".kimi-code" / "plugins" / "managed" / "usage-pulse")
    assert entries[0]["source"] == "local-path"
    assert "path" not in entries[0]
    assert "name" not in entries[0]
    assert not (tmp_path / ".kimi-code" / "mcp.json").exists()

    receipt = install.Receipt(installed_at="now", source=str(source))
    install.install_provider("kimi", source, receipt)
    installed_again = json.loads(
        (tmp_path / ".kimi-code" / "plugins" / "installed.json").read_text(encoding="utf-8")
    )
    assert len([p for p in installed_again["plugins"] if p.get("id") == "usage-pulse"]) == 1

    monkeypatch.setattr(sys, "argv", ["uninstall.py"])
    uninstall.main()
    assert not (tmp_path / ".usage-pulse" / "install-receipt.json").exists()
