from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--receipt", default=str(Path.home() / ".usage-pulse" / "install-receipt.json")
    )
    args = parser.parse_args()
    receipt_path = Path(args.receipt)
    if not receipt_path.exists():
        print(json.dumps({"uninstalled": False, "reason": "receipt not found"}))
        return
    receipt: dict[str, Any] = json.loads(receipt_path.read_text(encoding="utf-8"))
    restored: list[str] = []
    removed: list[str] = []
    for target, backup in receipt.get("backups", {}).items():
        target_path = Path(target)
        backup_path = Path(backup)
        if backup_path.exists():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_path, target_path)
            restored.append(str(target_path))
    for copy in receipt.get("copies", []):
        path = Path(copy)
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            removed.append(str(path))
        elif path.exists():
            path.unlink()
            removed.append(str(path))
    receipt_path.unlink()
    print(json.dumps({"uninstalled": True, "restored": restored, "removed": removed}))


if __name__ == "__main__":
    main()
