from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.utils.paths import ensure_subdirs
from ovarian_ai.utils.run_status import write_status


FIELDS = [
    "gene",
    "axis",
    "source",
    "tumor_expression",
    "normal_tissue_penalty",
    "cnv_support",
    "methylation_support",
    "survival_support",
    "depmap_dependency",
    "drug_sensitivity",
    "malignant_cell_specificity",
    "immune_cell_source",
    "spatial_support",
    "ligand_receptor_support",
    "virtual_ko_support",
    "independent_dataset_count",
    "functional_evidence",
    "negative_evidence",
    "novelty_score",
    "wetlab_feasibility",
    "evidence_level",
    "evidence_coverage",
    "total_score",
    "decision",
    "decision_reason",
]


AXES = {
    "SPP1": "SPP1-CD44/ITGB1 myeloid-malignant interaction",
    "CD44": "SPP1-CD44 receptor arm",
    "ITGB1": "SPP1-ITGB1 receptor arm",
    "MMP14": "matrix remodeling / invasion",
    "CD209": "DC-SIGN macrophage niche",
    "C1QA": "C1Q macrophage niche",
    "C1QB": "C1Q macrophage niche",
    "C1QC": "C1Q macrophage niche",
}


def status_from_detection(value) -> str:
    try:
        numeric = float(value)
    except Exception:
        return "NOT_TESTED"
    if numeric >= 0.05:
        return "SUPPORTED"
    if numeric == 0:
        return "NEGATIVE"
    return "INSUFFICIENT_DATA"


def build_rows(gse_dir: Path) -> list[dict]:
    key_path = gse_dir / "key_gene_expression_by_tissue.tsv"
    if not key_path.exists():
        return [
            {
                "gene": gene,
                "axis": axis,
                "source": "GSE319733",
                "tumor_expression": "NOT_TESTED",
                "normal_tissue_penalty": "NOT_TESTED",
                "cnv_support": "NOT_TESTED",
                "methylation_support": "NOT_TESTED",
                "survival_support": "NOT_TESTED",
                "depmap_dependency": "NOT_TESTED",
                "drug_sensitivity": "NOT_TESTED",
                "malignant_cell_specificity": "NOT_TESTED",
                "immune_cell_source": "NOT_TESTED",
                "spatial_support": "NOT_TESTED",
                "ligand_receptor_support": "NOT_TESTED",
                "virtual_ko_support": "NOT_TESTED",
                "independent_dataset_count": 0,
                "functional_evidence": "NOT_TESTED",
                "negative_evidence": "",
                "novelty_score": "INSUFFICIENT_DATA",
                "wetlab_feasibility": "NOT_TESTED",
                "evidence_level": "insufficient",
                "evidence_coverage": "GSE319733 not parsed",
                "total_score": "",
                "decision": "INSUFFICIENT_DATA",
                "decision_reason": "No parsed expression table available for this run.",
            }
            for gene, axis in AXES.items()
        ]
    df = pd.read_csv(key_path, sep="\t")
    rows = []
    for gene, axis in AXES.items():
        sub = df[df["gene"].str.upper() == gene]
        max_detection = pd.to_numeric(sub.get("detection_rate"), errors="coerce").max() if not sub.empty else None
        expr_status = status_from_detection(max_detection)
        independent_dataset_count = 1 if expr_status == "SUPPORTED" else 0
        total_score = 20 if expr_status == "SUPPORTED" else 5 if expr_status == "INSUFFICIENT_DATA" else 0
        decision = "NOT_TESTED"
        reason = "Only GSE319733 exploratory evidence is available; no independent validation yet."
        if expr_status == "NEGATIVE":
            decision = "NEGATIVE"
            reason = "GSE319733 parsed data did not support detectable expression at current threshold."
        elif expr_status == "SUPPORTED":
            decision = "INSUFFICIENT_DATA"
            reason = "Exploratory expression support exists but lacks two independent evidence sources and patient-level validation."
        rows.append(
            {
                "gene": gene,
                "axis": axis,
                "source": "GSE319733",
                "tumor_expression": expr_status,
                "normal_tissue_penalty": "NOT_TESTED",
                "cnv_support": "NOT_TESTED",
                "methylation_support": "NOT_TESTED",
                "survival_support": "NOT_TESTED",
                "depmap_dependency": "NOT_TESTED",
                "drug_sensitivity": "NOT_TESTED",
                "malignant_cell_specificity": "INSUFFICIENT_DATA",
                "immune_cell_source": expr_status if gene in {"SPP1", "CD209", "C1QA", "C1QB", "C1QC"} else "NOT_TESTED",
                "spatial_support": "NOT_TESTED",
                "ligand_receptor_support": "INSUFFICIENT_DATA" if gene in {"SPP1", "CD44", "ITGB1"} else "NOT_TESTED",
                "virtual_ko_support": "NOT_TESTED",
                "independent_dataset_count": independent_dataset_count,
                "functional_evidence": "NOT_TESTED",
                "negative_evidence": "" if expr_status != "NEGATIVE" else "Low/absent detection in parsed GSE319733 cells.",
                "novelty_score": "NOT_TESTED",
                "wetlab_feasibility": "medium" if gene in {"SPP1", "CD44", "ITGB1", "MMP14"} else "NOT_TESTED",
                "evidence_level": "exploratory" if expr_status == "SUPPORTED" else "insufficient",
                "evidence_coverage": "single dataset only",
                "total_score": total_score,
                "decision": decision,
                "decision_reason": reason,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "paths.yaml")
    args = parser.parse_args()
    dirs = ensure_subdirs(args.config)
    gse_dir = dirs["results"] / "scrna" / "GSE319733" / args.run_id
    out_dir = dirs["results"] / "target_factory" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = build_rows(gse_dir)
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
