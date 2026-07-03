from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

PLUGIN_NAME = "usage-pulse"
MARKER_START = "# >>> usage-pulse managed block"
MARKER_END = "# <<< usage-pulse managed block"


@dataclass
class Receipt:
    installed_at: str
    source: str
    copies: list[str] = field(default_factory=list)
    backups: dict[str, str] = field(default_factory=dict)
    original_hashes: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.__dict__, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["all", "claude", "codex", "kimi"], default="all")
    parser.add_argument("--source", default=str(repo_root()))
    args = parser.parse_args()
    source = Path(args.source).resolve()
    receipt = Receipt(installed_at=timestamp(), source=str(source))
    providers = ["claude", "codex", "kimi"] if args.provider == "all" else [args.provider]
    try:
        for provider in providers:
            install_provider(provider, source, receipt)
        receipt.save(receipt_path())
    except Exception:
        rollback(receipt)
        raise
    print(
        json.dumps(
            {"installed": providers, "receipt": str(receipt_path()), "warnings": receipt.warnings}
        )
    )


def install_provider(provider: str, source: Path, receipt: Receipt) -> None:
    if provider == "claude":
        install_claude(source, receipt)
    elif provider == "codex":
        install_codex(source, receipt)
    elif provider == "kimi":
        install_kimi(source, receipt)


def install_claude(source: Path, receipt: Receipt) -> None:
    home = Path.home()
    dest = Path(
        os.environ.get("USAGE_PULSE_CLAUDE_PLUGIN_DIR", home / ".claude" / "skills" / PLUGIN_NAME)
    )
    copy_plugin(source, dest, receipt)
    command_dest = Path(
        os.environ.get("USAGE_PULSE_CLAUDE_COMMAND", home / ".claude" / "commands" / "pulse.md")
    )
    copy_file(source / "commands" / "pulse.md", command_dest, receipt)


def install_codex(source: Path, receipt: Receipt) -> None:
    home = Path.home()
    dest = Path(os.environ.get("USAGE_PULSE_CODEX_PLUGIN_DIR", home / "plugins" / PLUGIN_NAME))
    copy_plugin(source, dest, receipt)
    marketplace = Path(
        os.environ.get(
            "USAGE_PULSE_CODEX_MARKETPLACE", home / ".agents" / "plugins" / "marketplace.json"
        )
    )
    data = read_json(marketplace)
    if not data:
        data = {"name": "personal", "interface": {"displayName": "Personal"}, "plugins": []}
    plugins = data.setdefault("plugins", [])
    entry = {
        "name": PLUGIN_NAME,
        "source": {"source": "local", "path": f"./plugins/{PLUGIN_NAME}"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Productivity",
    }
    plugins[:] = [item for item in plugins if item.get("name") != PLUGIN_NAME]
    plugins.append(entry)
    write_json_transactional(marketplace, data, receipt)
    config = Path(os.environ.get("USAGE_PULSE_CODEX_CONFIG", home / ".codex" / "config.toml"))
    append_toml_block(config, codex_toml_block(dest), receipt)
    run_optional(["codex", "plugin", "add", "usage-pulse@personal"], receipt)


def install_kimi(source: Path, receipt: Receipt) -> None:
    home = Path.home()
    kimi_home = Path(os.environ.get("KIMI_CODE_HOME", home / ".kimi-code"))
    dest = Path(
        os.environ.get(
            "USAGE_PULSE_KIMI_PLUGIN_DIR",
            kimi_home / "plugins" / "managed" / PLUGIN_NAME,
        )
    )
    copy_plugin(source, dest, receipt)
    skills_dest = Path(os.environ.get("USAGE_PULSE_KIMI_SKILLS_DIR", kimi_home / "skills"))
    copy_plugin(source / "skills" / "usage-report", skills_dest / "usage-report", receipt)
    copy_plugin(source / "skills" / "using-pulse", skills_dest / "using-pulse", receipt)
    installed = Path(
        os.environ.get("USAGE_PULSE_KIMI_INSTALLED", kimi_home / "plugins" / "installed.json")
    )
    installed_data = read_json(installed)
    installed_data.setdefault("version", 1)
    raw_plugins = installed_data.get("plugins")
    plugins = raw_plugins if isinstance(raw_plugins, list) else []
    prior = next(
        (
            item
            for item in plugins
            if isinstance(item, dict)
            and (item.get("id") == PLUGIN_NAME or item.get("name") == PLUGIN_NAME)
        ),
        None,
    )
    now = timestamp()
    plugin_entry = {
        "id": PLUGIN_NAME,
        "root": str(dest),
        "source": "local-path",
        "enabled": True,
        "installedAt": prior.get("installedAt", now) if isinstance(prior, dict) else now,
        "updatedAt": now,
        "originalSource": str(source),
    }
    installed_data["plugins"] = [
        item
        for item in plugins
        if not (
            isinstance(item, dict)
            and (item.get("id") == PLUGIN_NAME or item.get("name") == PLUGIN_NAME)
        )
    ]
    installed_data["plugins"].append(plugin_entry)
    write_json_transactional(installed, installed_data, receipt)


def mcp_config(dest: Path) -> dict[str, Any]:
    return {"command": "uv", "args": ["run", "--project", str(dest), "usage-pulse-mcp"]}


def add_claude_hook(hooks: dict[str, Any], event: str, command: str) -> None:
    items = hooks.setdefault(event, [])
    matcher = ".*" if event in {"PreToolUse", "PostToolUse"} else ""
    existing = json.dumps(items)
    if command in existing:
        return
    hook = {"type": "command", "command": command, "timeout": 10}
    item: dict[str, Any] = {"hooks": [hook]}
    if matcher:
        item["matcher"] = matcher
    items.append(item)


def hook_command(dest: Path, event: str, provider: str) -> str:
    script = {
        "SessionStart": "session_start.py",
        "UserPromptSubmit": "user_prompt_submit.py",
        "PreToolUse": "pre_tool_use.py",
        "PostToolUse": "post_tool_use.py",
        "PostToolUseFailure": "post_tool_use.py",
        "PreCompact": "pre_compact.py",
        "Stop": "stop.py",
        "SessionEnd": "session_end.py",
        "SubagentStart": "session_start.py",
    }.get(event, "session_start.py")
    code = (
        "import runpy,sys;"
        f"root={str(dest)!r};"
        "sys.path.insert(0, root + r'\\src');"
        f"sys.argv=['usage-pulse-hook',{event!r},'--provider',{provider!r}];"
        f"runpy.run_path(root + r'\\hooks\\{script}', run_name='__main__')"
    )
    return f'py -3 -c "{code}"'


def codex_toml_block(dest: Path) -> str:
    return "\n".join(
        [
            MARKER_START,
            '[plugins."usage-pulse@personal"]',
            "enabled = true",
            MARKER_END,
            "",
        ]
    )


def kimi_toml_block(dest: Path) -> str:
    lines = [MARKER_START]
    events = [
        ("SessionStart", ""),
        ("UserPromptSubmit", ""),
        ("PreToolUse", ".*"),
        ("PostToolUse", ".*"),
        ("PostToolUseFailure", ".*"),
        ("PreCompact", ""),
        ("Stop", ""),
        ("SessionEnd", ""),
        ("SubagentStart", ""),
    ]
    for event, matcher in events:
        lines.extend(
            [
                "[[hooks]]",
                f'event = "{event}"',
                f"command = {toml_string(hook_command(dest, event, 'kimi'))}",
                "timeout = 10",
            ]
        )
        if matcher:
            lines.append(f'matcher = "{matcher}"')
        lines.append("")
    lines.append(MARKER_END)
    lines.append("")
    return "\n".join(lines)


def append_toml_block(path: Path, block: str, receipt: Receipt) -> None:
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    prepare_backup(path, receipt)
    stripped = remove_marker_block(original)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stripped.rstrip() + "\n\n" + block, encoding="utf-8")


def remove_marker_block(text: str) -> str:
    start = text.find(MARKER_START)
    if start == -1:
        return text
    end = text.find(MARKER_END, start)
    if end == -1:
        return text[:start]
    return text[:start] + text[end + len(MARKER_END) :]


def copy_plugin(source: Path, dest: Path, receipt: Receipt) -> None:
    ignore = shutil.ignore_patterns(
        ".git",
        ".recall",
        ".codex_memory",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    )
    existed = dest.exists()
    shutil.copytree(source, dest, ignore=ignore, dirs_exist_ok=True)
    if not existed:
        receipt.copies.append(str(dest))


def copy_file(source: Path, dest: Path, receipt: Receipt) -> None:
    existed = dest.exists()
    if dest.exists():
        prepare_backup(dest, receipt)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    if not existed:
        receipt.copies.append(str(dest))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return {}
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def write_json_transactional(path: Path, data: dict[str, Any], receipt: Receipt) -> None:
    prepare_backup(path, receipt)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".usage-pulse.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def prepare_backup(path: Path, receipt: Receipt) -> None:
    key = str(path)
    if key in receipt.backups:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    receipt.original_hashes[key] = sha_file(path) if path.exists() else ""
    backup = path.with_name(f"{path.name}.usage-pulse.bak-{int(time.time())}")
    if path.exists():
        shutil.copy2(path, backup)
    else:
        backup.write_text("", encoding="utf-8")
    receipt.backups[key] = str(backup)


def rollback(receipt: Receipt) -> None:
    for target, backup in receipt.backups.items():
        backup_path = Path(backup)
        target_path = Path(target)
        if backup_path.exists() and backup_path.read_text(encoding="utf-8", errors="ignore"):
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_path, target_path)
    for copy in receipt.copies:
        path = Path(copy)
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            path.unlink()


def run_optional(args: list[str], receipt: Receipt) -> None:
    try:
        result = subprocess.run(args, check=False, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        receipt.warnings.append(f"{args[0]} CLI not found; config files were patched directly.")
        return
    except subprocess.TimeoutExpired:
        receipt.warnings.append(f"{args[0]} command timed out; config files were patched directly.")
        return
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        receipt.warnings.append(f"{' '.join(args[:3])} exited {result.returncode}: {stderr[:200]}")


def toml_string(value: str) -> str:
    return json.dumps(value)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def receipt_path() -> Path:
    return Path.home() / ".usage-pulse" / "install-receipt.json"


def timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha_file(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
