from __future__ import annotations

import argparse
import csv
import gzip
import re
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.utils.paths import ensure_subdirs
from ovarian_ai.utils.run_status import evaluate_quality_gate, write_status


FIELDS = [
    "patient_id",
    "biological_sample_id",
    "tissue_type",
    "tissue_code",
    "gex_gsm",
    "vdj_gsm",
    "gex_matrix",
    "gex_barcodes",
    "gex_features",
    "cell_metadata",
    "vdj_contigs",
    "has_gex",
    "has_vdj",
    "paired_patient",
    "metadata_source",
    "metadata_confidence",
]


def read_tsv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def gsm_from_name(name: str) -> str:
    match = re.match(r"(GSM\d+)_", name)
    return match.group(1) if match else ""


def sample_key(row: dict) -> tuple[str, str]:
    patient = row.get("patient_id", "")
    tissue = row.get("tissue", "")
    if not patient or not tissue:
        name = row.get("filename", "")
        patient_match = re.search(r"_(P\d+)_", name)
        tissue_match = re.search(r"_(LN|PT)_", name)
        patient = patient or (patient_match.group(1) if patient_match else "")
        tissue = tissue or (tissue_match.group(1) if tissue_match else "")
    return patient, tissue


def metadata_has_rows(path: str) -> bool:
    if not path:
        return False
    try:
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
            return sum(1 for _ in handle) > 1
    except Exception:
        return False


def build_manifest(extracted_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    grouped: dict[tuple[str, str], dict] = defaultdict(dict)
    errors = []
    for row in extracted_rows:
        patient, tissue = sample_key(row)
        if not patient or not tissue:
            errors.append({"filename": row.get("filename", ""), "error": "missing patient or tissue in filename"})
            continue
        item = grouped[(patient, tissue)]
        item.setdefault("patient_id", patient)
        item.setdefault("tissue_code", tissue)
        item.setdefault("tissue_type", "tumor-draining lymph node" if tissue == "LN" else "primary tumor" if tissue == "PT" else "unknown")
        item.setdefault("biological_sample_id", f"{patient}_{tissue}")
        file_type = row.get("file_type", "")
        if file_type in {"gex_matrix", "gex_barcodes", "gex_features", "cell_metadata"}:
            item["gex_gsm"] = item.get("gex_gsm") or gsm_from_name(row.get("filename", ""))
        if file_type == "vdj_contigs":
            item["vdj_gsm"] = item.get("vdj_gsm") or gsm_from_name(row.get("filename", ""))
        mapping = {
            "gex_matrix": "gex_matrix",
            "gex_barcodes": "gex_barcodes",
            "gex_features": "gex_features",
            "cell_metadata": "cell_metadata",
            "vdj_contigs": "vdj_contigs",
        }
        if file_type in mapping:
            target_field = mapping[file_type]
            if item.get(target_field) and item[target_field] != row.get("local_path"):
                errors.append({"filename": row.get("filename", ""), "error": f"duplicate {target_field} for {patient}_{tissue}"})
            item[target_field] = row.get("local_path", "")

    patients = defaultdict(set)
    for patient, tissue in grouped:
        patients[patient].add(tissue)
    rows = []
    for key in sorted(grouped):
        item = grouped[key]
        item["has_gex"] = str(bool(item.get("gex_matrix") and item.get("gex_barcodes") and item.get("gex_features"))).lower()
        item["has_vdj"] = str(bool(item.get("vdj_contigs"))).lower()
        item["paired_patient"] = str({"LN", "PT"}.issubset(patients[item["patient_id"]])).lower()
        item["metadata_source"] = "GEO_Metadata_csv;filename"
        item["metadata_confidence"] = "high" if metadata_has_rows(item.get("cell_metadata", "")) else "medium"
        rows.append({field: item.get(field, "") for field in FIELDS})
    return rows, errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "paths.yaml")
    args = parser.parse_args()
    dirs = ensure_subdirs(args.config)
    out_dir = dirs["results"] / "scrna" / "GSE319733" / args.run_id
    extracted = out_dir / "extracted_file_manifest.tsv"
    rows = read_tsv(extracted) if extracted.exists() else []
    manifest, errors = build_manifest(rows)
    manifest_path = out_dir / "sample_manifest.tsv"
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter="\t")
        writer.writeheader()
        writer.writerows(manifest)
    with (out_dir / "sample_manifest_errors.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["filename", "error"], delimiter="\t")
        writer.writeheader()
        writer.writerows(errors)
    paired = sorted({row["patient_id"] for row in manifest if row["paired_patient"] == "true"})
    validation_lines = [
        "# GSE319733 Sample Manifest Validation",
        "",
        f"- biological_sample_rows: {len(manifest)}",
        f"- unique_biological_sample_ids: {len({row['biological_sample_id'] for row in manifest})}",
        f"- paired_patients: {', '.join(paired)}",
        f"- expected_P1_P4_paired_confirmed: {str(all(patient in paired for patient in ['P1', 'P2', 'P3', 'P4'])).lower()}",
        f"- metadata_confidence_all_low: {str(all(row['metadata_confidence'] == 'low' for row in manifest)).lower()}",
        f"- errors: {len(errors)}",
    ]
    (out_dir / "sample_manifest_validation.md").write_text("\n".join(validation_lines) + "\n", encoding="utf-8")
    gate = evaluate_quality_gate([str(manifest_path)], [str(manifest_path)])
    status = "COMPLETED" if gate["quality_gate_passed"] and all(patient in paired for patient in ["P1", "P2", "P3", "P4"]) else "INSUFFICIENT_DATA"
    write_status(out_dir / "sample_manifest_status.json", "GSE319733_sample_manifest", status, run_id=args.run_id, **gate, errors=errors)
    print(manifest_path)


if __name__ == "__main__":
    main()
