from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.scoring.evidence_table import FIELDS, build_candidate_rows
from ovarian_ai.utils.paths import ensure_subdirs
from ovarian_ai.utils.run_status import write_status


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "paths.yaml")
    args = parser.parse_args()
    dirs = ensure_subdirs(args.config)
    gse_dir = dirs["results"] / "scrna" / "GSE319733" / args.run_id
    out_dir = dirs["results"] / "target_factory" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = build_candidate_rows(gse_dir, dirs["results"] / "dataset_feasibility" / args.run_id / "GSE338829_download_decision.json")
    out_path = out_dir / "candidate_target_table.tsv"
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    status = "COMPLETED_WITH_WARNINGS" if any(row["decision"] == "INSUFFICIENT_DATA" for row in rows) else "COMPLETED"
    write_status(out_dir / "status.json", "target_factory", status, run_id=args.run_id, outputs=[str(out_path)])
    print(out_path)


if __name__ == "__main__":
    main()
