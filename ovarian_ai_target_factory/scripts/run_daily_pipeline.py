from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.datasets.dataset_watcher import run as run_dataset
from ovarian_ai.literature.literature_watcher import run as run_literature
from ovarian_ai.report.report_generator import run as run_report
from ovarian_ai.utils.paths import daily_reports_root, ensure_subdirs


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MVP daily ovarian AI target pipeline.")
    parser.add_argument("--date", dest="run_date", default=date.today().isoformat())
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "paths.yaml")
    parser.add_argument("--retmax", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ensure_subdirs(args.config)
    outdir = daily_reports_root(args.config)
    run_literature(args.run_date, args.config, outdir, args.dry_run, args.retmax)
    run_dataset(args.run_date, args.config, outdir, args.dry_run, args.retmax)
    run_report("daily", args.run_date, args.config, outdir, args.dry_run)
    print(f"daily pipeline output: {outdir}")


if __name__ == "__main__":
    main()
