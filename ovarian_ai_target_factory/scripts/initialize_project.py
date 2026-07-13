from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.utils.paths import ensure_subdirs


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize D-drive project data directories.")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "paths.yaml")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        print("initialize_project dry run: no directories changed")
        return

    dirs = ensure_subdirs(args.config)
    for name, path in dirs.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
