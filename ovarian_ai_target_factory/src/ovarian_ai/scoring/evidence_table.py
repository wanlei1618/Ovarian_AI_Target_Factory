from __future__ import annotations

from pathlib import Path

import pandas as pd


EVIDENCE_STATES = {"SUPPORTED", "NEGATIVE", "NOT_TESTED", "INSUFFICIENT_DATA"}

FIELDS = [
    "gene",
    "axis",
    "source_dataset",
    "evidence_type",
    "tumor_expression",
    "normal_tissue_penalty",
    "cnv_support",
    "survival_support",
    "depmap_dependency",
    "drug_sensitivity",
    "malignant_cell_specificity",
    "immune_cell_source",
    "spatial_support",
    "ligand_receptor_support",
    "virtual_ko_support",
    "functional_perturbation",
    "independent_dataset_count",
    "negative_evidence",
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
    "RBMS1": "RBMS1-NEDD4 perturbation validation",
    "NEDD4": "RBMS1-NEDD4 perturbation validation",
}


def detection_to_state(value) -> str:
    try:
        numeric = float(value)
    except Exception:
        return "NOT_TESTED"
    if numeric >= 0.05:
        return "SUPPORTED"
    if numeric == 0:
        return "NEGATIVE"
    return "INSUFFICIENT_DATA"


def missing_evidence_row(gene: str, reason: str) -> dict:
    return {
        "gene": gene,
        "axis": AXES[gene],
        "source_dataset": "GSE319733;GSE338829",
        "evidence_type": "expression_or_perturbation",
        "tumor_expression": "NOT_TESTED",
        "normal_tissue_penalty": "NOT_TESTED",
        "cnv_support": "NOT_TESTED",
        "survival_support": "NOT_TESTED",
        "depmap_dependency": "NOT_TESTED",
        "drug_sensitivity": "NOT_TESTED",
        "malignant_cell_specificity": "NOT_TESTED",
        "immune_cell_source": "NOT_TESTED",
        "spatial_support": "NOT_TESTED",
        "ligand_receptor_support": "NOT_TESTED",
        "virtual_ko_support": "NOT_TESTED",
        "functional_perturbation": "NOT_TESTED",
        "independent_dataset_count": "0",
        "negative_evidence": "",
        "evidence_coverage": "INSUFFICIENT_DATA",
        "total_score": "",
        "decision": "INSUFFICIENT_DATA",
        "decision_reason": reason,
    }


def build_candidate_rows(gse319733_dir: Path, gse338829_decision: Path | None = None) -> list[dict]:
    key_path = gse319733_dir / "key_gene_expression_by_celltype.tsv"
    if not key_path.exists():
        key_path = gse319733_dir / "key_gene_expression_by_tissue.tsv"
    if not key_path.exists() or key_path.stat().st_size == 0:
        return [missing_evidence_row(gene, "No parsed expression table is available for this run.") for gene in AXES]

    df = pd.read_csv(key_path, sep="\t")
    rows = []
    for gene in AXES:
        sub = df[df["gene"].astype(str).str.upper() == gene]
        max_detection = pd.to_numeric(sub.get("detection_rate"), errors="coerce").max() if not sub.empty else None
        expression_state = detection_to_state(max_detection)
        row = missing_evidence_row(gene, "Exploratory parsed evidence is insufficient for target promotion.")
        row["tumor_expression"] = expression_state
        row["source_dataset"] = "GSE319733"
        row["independent_dataset_count"] = "1" if expression_state == "SUPPORTED" else "0"
        row["immune_cell_source"] = expression_state if gene in {"SPP1", "CD209"} else "NOT_TESTED"
        row["ligand_receptor_support"] = "INSUFFICIENT_DATA" if gene in {"SPP1", "CD44", "ITGB1"} and expression_state == "SUPPORTED" else "NOT_TESTED"
        row["evidence_coverage"] = "single_dataset_exploratory" if expression_state == "SUPPORTED" else "INSUFFICIENT_DATA"
        if expression_state == "NEGATIVE":
            row["decision"] = "NEGATIVE"
            row["negative_evidence"] = "Low/absent detection in parsed GSE319733 cells."
        elif expression_state == "SUPPORTED":
            row["decision"] = "INSUFFICIENT_DATA"
            row["total_score"] = "20"
        rows.append(row)
    return rows
