"""Small Kimi plugin tool wrapper."""

from __future__ import annotations

import json
import sys

from usage_pulse.db import PulseDB


def main() -> None:
    _ = sys.stdin.read()
    command = sys.argv[1] if len(sys.argv) > 1 else "today"
    if command == "today":
        print(json.dumps(PulseDB().today()))
    else:
        print(json.dumps({"summary": f"Unknown usage-pulse command: {command}"}))


if __name__ == "__main__":
    main()
