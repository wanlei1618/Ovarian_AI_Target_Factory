from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.scoring.evidence_table import EVIDENCE_RECORD_FIELDS, FIELDS, build_candidate_rows_from_records, build_evidence_records
from ovarian_ai.utils.paths import ensure_subdirs
from ovarian_ai.utils.run_status import write_status


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "paths.yaml")
    parser.add_argument("--analysis-code-sha", default="")
    args = parser.parse_args()
    dirs = ensure_subdirs(args.config)
    gse_dir = dirs["results"] / "scrna" / "GSE319733" / args.run_id
    out_dir = dirs["results"] / "target_factory" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    feasibility_dir = dirs["results"] / "dataset_feasibility" / args.run_id
    evidence_records = build_evidence_records(gse_dir, feasibility_dir, args.analysis_code_sha, args.run_id)
    evidence_path = out_dir / "evidence_records.tsv"
    with evidence_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=EVIDENCE_RECORD_FIELDS, delimiter="\t")
        writer.writeheader()
        writer.writerows(evidence_records)
    rows = build_candidate_rows_from_records(evidence_records)
    out_path = out_dir / "candidate_target_table.tsv"
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    status = "COMPLETED_WITH_WARNINGS" if any(row["decision"] == "INSUFFICIENT_DATA" for row in rows) else "COMPLETED"
    write_status(out_dir / "status.json", "target_factory", status, run_id=args.run_id, outputs=[str(evidence_path), str(out_path)], row_counts={"evidence_records": len(evidence_records), "candidate_target_table": len(rows)}, quality_gate_passed=bool(evidence_records))
    print(out_path)


if __name__ == "__main__":
    main()
