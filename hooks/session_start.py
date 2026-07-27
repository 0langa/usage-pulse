import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
if len(sys.argv) == 1:
    sys.argv.append("SessionStart")

from usage_pulse.hooks import main

if __name__ == "__main__":
    main()
