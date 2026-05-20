from __future__ import annotations

import os
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = WORKSPACE_ROOT / "_runtime" / "flock" / "worker_team_prototype.py"
PROTOTYPE_RELATIVE = Path("_runtime") / "flock" / "worker_team_prototype.py"


def main() -> None:
    if not PROTOTYPE.is_file():
        raise SystemExit(f"Missing runtime prototype: {PROTOTYPE}")
    os.chdir(WORKSPACE_ROOT)
    os.execv(sys.executable, [sys.executable, str(PROTOTYPE_RELATIVE), *sys.argv[1:]])


if __name__ == "__main__":
    main()
