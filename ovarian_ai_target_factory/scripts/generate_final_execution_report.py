from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.utils.paths import ensure_subdirs
from ovarian_ai.utils.run_status import write_status


def read_status(path: Path) -> str:
    if not path.exists():
        return "NOT_STARTED"
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("analysis_status", "UNKNOWN")
    except Exception:
        return "UNKNOWN"


def git_output(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git"] + args, cwd=str(REPO_ROOT), text=True).strip()
    except Exception:
        return "unavailable"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "paths.yaml")
    args = parser.parse_args()
    dirs = ensure_subdirs(args.config)
    out_dir = dirs["results"] / "final_reports" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    phase0 = read_status(dirs["results"] / "pipeline_qc" / args.run_id / "status.json")
    gse = read_status(dirs["results"] / "scrna" / "GSE319733" / args.run_id / "status.json")
    feasibility = read_status(dirs["results"] / "dataset_feasibility" / args.run_id / "status.json")
    target = read_status(dirs["results"] / "target_factory" / args.run_id / "status.json")
    sync_dir = PROJECT_ROOT / "results_synced"
    lines = [
        "# Final Execution Report",
        "",
        f"- run_id: {args.run_id}",
        f"- git_branch: {git_output(['branch', '--show-current'])}",
        f"- local_git_sha: {git_output(['rev-parse', 'HEAD'])}",
        f"- remote_branch: codex/improve-after-20260724",
        f"- remote_main_note: GitHub sync is performed with lightweight result copies; no force push is used.",
        "",
        "## Module Status",
        f"- Phase 0 environment / Rscript / disk / Git precheck: {phase0}",
        "- Phase 1 pipeline realism and report logic: COMPLETED_WITH_WARNINGS",
        f"- Phase 2 GSE337706/GSE338829 feasibility: {feasibility}",
        f"- Phase 2 GSE319733 GEX/BCR analysis: {gse}",
        f"- Phase 3 minimal target evidence factory: {target}",
        "- Phase 4 lightweight GitHub sync: RUNNING_OR_PENDING",
        "",
        "## Completed Modules",
        "- Separated raw GEO hits, daily newly detected datasets, curated dataset registry, and refined dataset registry.",
        "- Fixed curated GSE262172 modality to ATAC-seq.",
        "- Updated daily report logic to use refined literature/dataset outputs.",
        "- Reclassified GSE337706 as ovarian liquid biopsy / platelet-coated CTC branch.",
        "- Checked GSE338829 as RBMS1-NEDD4 perturbation-validation feasibility branch.",
        "- Created real GSE319733 supplementary file inventory from GEO.",
        "- Added target evidence table with NOT_TESTED / NEGATIVE / INSUFFICIENT_DATA semantics.",
        "- Added lightweight GitHub sync script and manifests.",
        "",
        "## Incomplete or Blocked Modules",
        "- GSE319733 expression/BCR matrix parsing is BLOCKED unless RAW.tar download is manually approved. GEO filelist names processed files, but individual files return 404 outside RAW.tar.",
        "- pytest was requested but is not installed in the current Python 3.7 environment; direct standard-library test execution was used.",
        "- No Target Cards generated because no candidate has two independent evidence sources plus patient-level support.",
        "",
        "## GSE319733 Suitability for SPP1 Main Axis",
        "- main_axis_eligibility: NO",
        "- reason: processed expression/VDJ matrices were not parsed because direct processed file URLs returned 404 and RAW.tar default download is disallowed.",
        "- branch_value: B-cell / tumor-draining lymph-node immune niche.",
        "",
        "## SPP1-CD44/ITGB1 Evidence",
        "- new_support: NOT_TESTED",
        "- contradictory_evidence: NOT_TESTED",
        "- untested_items: patient-level expression, malignant epithelial specificity, myeloid SPP1 source, CD44/ITGB1 receptor localization, paired pseudobulk support.",
        "",
        "## Candidate Ranking",
        "- See `candidate_target_table.tsv` under target_factory.",
        "- SPP1, CD44, ITGB1, MMP14 are retained as exploratory inputs only; no high-score assignment was made.",
        "",
        "## Key D-Drive Paths",
        f"- raw data: {dirs['raw']}",
        f"- processed data: {dirs['processed']}",
        f"- results: {dirs['results']}",
        f"- cache: {dirs['cache']}",
        f"- logs: {dirs['logs']}",
        "",
        "## GitHub Sync Directories",
        f"- pipeline_qc: {sync_dir / 'pipeline_qc' / args.run_id}",
        f"- daily_reports: {sync_dir / 'daily_reports' / args.run_id}",
        f"- scrna/GSE319733: {sync_dir / 'scrna' / 'GSE319733' / args.run_id}",
        f"- dataset_feasibility: {sync_dir / 'dataset_feasibility' / args.run_id}",
        f"- target_factory: {sync_dir / 'target_factory' / args.run_id}",
        f"- final_reports: {sync_dir / 'final_reports' / args.run_id}",
        "",
        "## Unsynced Large Files",
        "- RAW.tar and all large raw sequencing formats are excluded by policy.",
        "- See `excluded_from_sync.tsv` after sync for file-level details.",
        "",
        "## Next Minimal Tasks",
        "- Decide whether downloading GSE319733_RAW.tar (336 MB) is allowed for processed matrix extraction.",
        "- If approved, extract only processed MTX/barcodes/features/VDJ contigs to D-drive raw data and rerun GSE319733 analysis.",
        "- Add one independent dataset before any Target Card generation.",
        "",
    ]
    report = out_dir / "Final_Execution_Report.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    write_status(out_dir / "status.json", "final_execution_report", "COMPLETED_WITH_WARNINGS", run_id=args.run_id, outputs=[str(report)])
    print(report)


if __name__ == "__main__":
    main()
