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

EVIDENCE_RECORD_FIELDS = [
    "gene",
    "axis",
    "source_dataset",
    "source_module",
    "evidence_type",
    "evidence_status",
    "direction",
    "effect_size",
    "statistic",
    "p_value",
    "fdr",
    "sample_count",
    "patient_count",
    "cell_type",
    "tissue",
    "evidence_level",
    "negative_evidence",
    "result_path",
    "analysis_code_sha",
    "run_id",
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


def build_evidence_records(gse319733_dir: Path, feasibility_dir: Path, analysis_code_sha: str, run_id: str) -> list[dict]:
    records = []
    axis_path = gse319733_dir / "candidate_axis_evidence.tsv"
    if axis_path.exists():
        df = pd.read_csv(axis_path, sep="\t")
        for _, row in df.iterrows():
            records.append(
                {
                    "gene": row.get("gene", ""),
                    "axis": row.get("axis", ""),
                    "source_dataset": "GSE319733",
                    "source_module": "GSE319733_GEX_patient_axis",
                    "evidence_type": "patient_level_expression",
                    "evidence_status": row.get("evidence_status", "INSUFFICIENT_DATA"),
                    "direction": row.get("direction", ""),
                    "effect_size": row.get("effect_size", ""),
                    "statistic": "",
                    "p_value": row.get("p_value", ""),
                    "fdr": row.get("fdr", ""),
                    "sample_count": row.get("sample_count", ""),
                    "patient_count": row.get("patient_count", ""),
                    "cell_type": row.get("cell_type", ""),
                    "tissue": row.get("tissue", ""),
                    "evidence_level": row.get("evidence_level", "exploratory"),
                    "negative_evidence": "" if row.get("evidence_status") != "NEGATIVE" else row.get("reason", ""),
                    "result_path": row.get("result_path", str(axis_path)),
                    "analysis_code_sha": analysis_code_sha,
                    "run_id": run_id,
                }
            )
    decision_path = feasibility_dir / "GSE338829" / "GSE338829_assay_classification.json"
    if decision_path.exists():
        import json

        payload = json.loads(decision_path.read_text(encoding="utf-8"))
        for gene in ("RBMS1", "NEDD4"):
            records.append(
                {
                    "gene": gene,
                    "axis": AXES[gene],
                    "source_dataset": "GSE338829",
                    "source_module": "GSE338829_assay_classification",
                    "evidence_type": payload.get("evidence_type", "RNA-binding target evidence"),
                    "evidence_status": "INSUFFICIENT_DATA",
                    "direction": "",
                    "effect_size": "",
                    "statistic": "",
                    "p_value": "",
                    "fdr": "",
                    "sample_count": payload.get("sample_count", ""),
                    "patient_count": "",
                    "cell_type": payload.get("cell_line", ""),
                    "tissue": "",
                    "evidence_level": "metadata_assay_scope",
                    "negative_evidence": "",
                    "result_path": str(decision_path),
                    "analysis_code_sha": analysis_code_sha,
                    "run_id": run_id,
                }
            )
    return records


def build_candidate_rows_from_records(records: list[dict]) -> list[dict]:
    by_gene: dict[str, list[dict]] = {}
    for record in records:
        by_gene.setdefault(record["gene"], []).append(record)
    rows = []
    for gene, axis in AXES.items():
        recs = by_gene.get(gene, [])
        if not recs:
            rows.append(missing_evidence_row(gene, "No evidence records available for this gene."))
            continue
        statuses = {record.get("evidence_status") for record in recs}
        supported = sum(1 for record in recs if record.get("evidence_status") == "SUPPORTED")
        negative = sum(1 for record in recs if record.get("evidence_status") == "NEGATIVE")
        datasets = {record.get("source_dataset") for record in recs if record.get("source_dataset")}
        row = missing_evidence_row(gene, "Evidence records are present but insufficient for promotion.")
        row["source_dataset"] = ";".join(sorted(datasets))
        row["evidence_type"] = ";".join(sorted({record.get("evidence_type", "") for record in recs if record.get("evidence_type")}))
        row["independent_dataset_count"] = str(len(datasets))
        row["evidence_coverage"] = f"{len([s for s in statuses if s in EVIDENCE_STATES and s != 'NOT_TESTED'])}/8"
        row["tumor_expression"] = "SUPPORTED" if supported else "NEGATIVE" if negative else "INSUFFICIENT_DATA"
        if negative and not supported:
            row["decision"] = "NEGATIVE"
            row["negative_evidence"] = "; ".join(record.get("negative_evidence", "") for record in recs if record.get("negative_evidence"))
        elif supported >= 1 and len(datasets) >= 2:
            row["decision"] = "KEEP_EXPLORATORY"
            row["total_score"] = "40"
        else:
            row["decision"] = "INSUFFICIENT_DATA"
        return_rows = row
        rows.append(return_rows)
    return rows


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
