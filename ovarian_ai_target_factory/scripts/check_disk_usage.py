from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.utils.paths import ensure_subdirs


def _gb(value: int) -> float:
    return round(value / (1024**3), 2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check disk placement for the MVP project.")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "paths.yaml")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    dirs = ensure_subdirs(args.config)
    root = dirs["root"]
    usage = shutil.disk_usage(root)
    c_usage = shutil.disk_usage("C:/")
    warnings = []
    for key in ("raw", "cache", "processed", "results"):
        if dirs[key].resolve().drive.upper() == "C:":
            warnings.append(f"WARNING: {key} is on C drive: {dirs[key]}")

    lines = [
        f"Disk check date: {date.today().isoformat()}",
        f"Data root: {root}",
        f"Data-root drive free GB: {_gb(usage.free)}",
        f"C drive free GB: {_gb(c_usage.free)}",
        *warnings,
    ]
    text = "\n".join(lines) + "\n"
    print(text, end="")

    if not args.dry_run:
        log_path = dirs["logs"] / f"disk_usage_{date.today().isoformat()}.log"
        log_path.write_text(text, encoding="utf-8")

    if warnings:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
