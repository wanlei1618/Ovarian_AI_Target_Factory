from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import re
import sys
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import mmread

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.utils.paths import ensure_subdirs
from ovarian_ai.utils.run_status import evaluate_quality_gate, sha256_file, write_status


BASE_URL = "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE319nnn/GSE319733/suppl"
SERIES_MATRIX_URL = "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE319nnn/GSE319733/matrix/GSE319733_series_matrix.txt.gz"
MARKERS = {
    "B_cell": ["MS4A1", "CD79A", "CD79B", "CD74"],
    "plasma_cell": ["MZB1", "JCHAIN", "XBP1", "IGHG1", "IGKC"],
    "T_cell": ["CD3D", "CD3E", "TRAC"],
    "myeloid": ["LST1", "C1QA", "C1QB", "SPP1", "APOE"],
    "malignant_epithelial": ["EPCAM", "KRT8", "KRT18", "KRT19", "MSLN"],
    "endothelial": ["PECAM1", "VWF"],
    "fibroblast_CAF": ["COL1A1", "COL1A2", "DCN", "ACTA2"],
}
KEY_GENES = ["MMP14", "CD79A", "MS4A1", "MZB1", "JCHAIN", "IGHG1", "IGKC", "EPCAM", "KRT8", "KRT18", "PTPRC", "SPP1", "CD44", "ITGB1"]


def fetch_bytes(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "OvarianAITargetFactory/next-analysis"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def url_exists(url: str, timeout: int = 12) -> tuple[bool, str]:
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "OvarianAITargetFactory/next-analysis"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status < 400, ""
    except Exception as exc:
        return False, str(exc)


def download(url: str, path: Path) -> None:
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "OvarianAITargetFactory/next-analysis"})
    with urllib.request.urlopen(req, timeout=30) as response, path.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)


def parse_filelist(text: str) -> list[dict]:
    rows = []
    reader = csv.DictReader(text.splitlines(), delimiter="\t")
    for row in reader:
        name = row.get("Name", "")
        if not name or name == "Name":
            continue
        size = int(row.get("Size") or 0)
        lower = name.lower()
        file_type = "raw_archive" if lower.endswith(".tar") else "matrix" if "matrix.mtx" in lower else "barcodes" if "barcodes" in lower else "features" if "features" in lower else "metadata" if "metadata" in lower else "vdj_contig" if "contig_annotations" in lower else row.get("Type", "")
        required_gex = file_type in {"matrix", "barcodes", "features", "metadata"}
        required_bcr = file_type == "vdj_contig"
        decision = "skip"
        reason = "not required"
        if file_type == "raw_archive":
            reason = "RAW.tar is explicitly excluded from default download"
        elif size > 5 * 1024**3:
            decision = "blocked"
            reason = "single file exceeds 5 GB manual approval threshold"
        elif required_gex or required_bcr:
            decision = "download"
            reason = "processed GEX/metadata/VDJ file required for lightweight analysis"
        rows.append(
            {
                "filename": name,
                "url": f"{BASE_URL}/{name}",
                "size_bytes": size,
                "size_gb": round(size / (1024**3), 4),
                "file_type": file_type,
                "likely_content": file_type,
                "required_for_gex": required_gex,
                "required_for_bcr": required_bcr,
                "download_decision": decision,
                "decision_reason": reason,
                "local_path": "",
                "source_container": "GSE319733_RAW.tar" if file_type != "raw_archive" else "",
                "sha256": "",
            }
        )
    return rows


def sample_from_name(name: str) -> dict:
    gsm = re.match(r"(GSM\d+)_", name)
    patient = re.search(r"_(P\d+)_", name)
    tissue = re.search(r"_(LN|PT)_", name)
    return {
        "sample_id": gsm.group(1) if gsm else "",
        "patient_id": patient.group(1) if patient else "",
        "tumor_or_tdln": tissue.group(1) if tissue else "",
        "tissue_type": "tumor-draining lymph node" if tissue and tissue.group(1) == "LN" else "primary tumor" if tissue and tissue.group(1) == "PT" else "unknown",
    }


def read_features(path: Path) -> list[str]:
    genes = []
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            genes.append(parts[1] if len(parts) > 1 else parts[0])
    return genes


def read_barcodes(path: Path) -> list[str]:
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
        return [line.strip() for line in handle if line.strip()]


def gini(values: list[int]) -> float:
    if not values:
        return 0.0
    arr = np.sort(np.asarray(values, dtype=float))
    n = arr.size
    if arr.sum() == 0:
        return 0.0
    return float((2 * np.arange(1, n + 1).dot(arr) / (n * arr.sum())) - (n + 1) / n)


def shannon(values: list[int]) -> float:
    total = sum(values)
    if total == 0:
        return 0.0
    probs = [v / total for v in values if v > 0]
    return float(-sum(p * math.log(p) for p in probs))


def infer_celltype(matrix, genes: list[str]) -> tuple[list[str], dict[str, float]]:
    gene_index = {g.upper(): i for i, g in enumerate(genes)}
    scores = {}
    for group, markers in MARKERS.items():
        idx = [gene_index[m] for m in markers if m in gene_index]
        if idx:
            arr = np.asarray(matrix[idx, :].mean(axis=0)).ravel()
        else:
            arr = np.zeros(matrix.shape[1])
        scores[group] = arr
    groups = list(scores)
    labels = []
    for col in range(matrix.shape[1]):
        best = max(groups, key=lambda group: scores[group][col])
        labels.append(best if scores[best][col] > 0 else "unknown")
    mean_scores = {group: float(np.mean(values)) for group, values in scores.items()}
    return labels, mean_scores


def analyze_sample(group: dict, raw_dir: Path) -> tuple[dict, list[dict], list[dict]]:
    sample = sample_from_name(group["matrix"])
    matrix_path = raw_dir / group["matrix"]
    feature_path = raw_dir / group["features"]
    barcode_path = raw_dir / group["barcodes"]
    genes = read_features(feature_path)
    barcodes = read_barcodes(barcode_path)
    matrix = mmread(str(matrix_path)).tocsr()
    if matrix.shape[0] != len(genes) and matrix.shape[1] == len(genes):
        matrix = matrix.T.tocsr()
    labels, marker_scores = infer_celltype(matrix, genes)
    gene_index = {g.upper(): i for i, g in enumerate(genes)}
    detected_gene_count = int((np.asarray(matrix.sum(axis=1)).ravel() > 0).sum())
    qc = {
        **sample,
        "platform": "10x Genomics",
        "estimated_cells": len(barcodes),
        "detected_gene_count": detected_gene_count,
        "nFeature_median": "",
        "nCount_median": "",
        "percent_mt_median": "",
        "doublet_estimate": "NOT_TESTED",
        "low_quality_cell_fraction": "NOT_TESTED",
        "source_file": group["matrix"],
    }
    marker_rows = [{**sample, "celltype_or_marker_group": group_name, "mean_marker_score": score, "cell_count_assigned": labels.count(group_name)} for group_name, score in marker_scores.items()]
    key_rows = []
    label_arr = np.asarray(labels)
    for gene in KEY_GENES:
        idx = gene_index.get(gene)
        for celltype in sorted(set(labels)):
            mask = label_arr == celltype
            if idx is None or not mask.any():
                mean_expr = ""
                detection = ""
            else:
                values = np.asarray(matrix[idx, mask].todense()).ravel()
                mean_expr = float(values.mean())
                detection = float((values > 0).mean())
            key_rows.append({**sample, "celltype": celltype, "gene": gene, "mean_expression": mean_expr, "detection_rate": detection})
    return qc, marker_rows, key_rows


def analyze_bcr(path: Path) -> dict:
    sample = sample_from_name(path.name)
    try:
        df = pd.read_csv(path, compression="gzip")
    except Exception:
        return {**sample, "valid_clonotype_count": 0, "expanded_clonotype_count": 0, "shannon": "", "gini": "", "status": "FAILED_READ"}
    productive_col = next((c for c in df.columns if c.lower() == "productive"), "")
    clone_col = next((c for c in df.columns if "clonotype" in c.lower()), "")
    if productive_col:
        df = df[df[productive_col].astype(str).str.lower().isin(["true", "t", "yes"])]
    counts = Counter(df[clone_col].dropna().astype(str)) if clone_col else Counter()
    vals = list(counts.values())
    return {**sample, "valid_clonotype_count": len(counts), "expanded_clonotype_count": sum(v > 1 for v in vals), "shannon": shannon(vals), "gini": gini(vals), "status": "COMPLETED"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "paths.yaml")
    parser.add_argument("--max-file-gb", type=float, default=5.0)
    args = parser.parse_args()
    dirs = ensure_subdirs(args.config)
    raw_dir = dirs["raw"] / "single_cell" / "GSE319733"
    out_dir = dirs["results"] / "scrna" / "GSE319733" / args.run_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    warnings = []
    errors = []

    filelist_path = raw_dir / "filelist.txt"
    try:
        filelist_path.write_bytes(fetch_bytes(f"{BASE_URL}/filelist.txt"))
        download(SERIES_MATRIX_URL, raw_dir / "GSE319733_series_matrix.txt.gz")
    except Exception as exc:
        errors.append(f"metadata download failed: {exc}")

    inventory = parse_filelist(filelist_path.read_text(encoding="utf-8", errors="replace")) if filelist_path.exists() else []
    extracted_dir = raw_dir / "processed_from_RAW"
    archive_only_layout = any(row["file_type"] == "raw_archive" for row in inventory)
    for row in inventory:
        if row["download_decision"] == "download":
            try:
                extracted = extracted_dir / row["filename"]
                if extracted.exists():
                    row["local_path"] = str(extracted)
                    row["sha256"] = sha256_file(extracted)
                    row["download_decision"] = "available_extracted"
                    row["decision_reason"] = "processed file already available from approved safe extraction"
                    continue
                if archive_only_layout:
                    row["download_decision"] = "blocked"
                    row["decision_reason"] = "archive-only GEO layout; processed member requires RAW.tar extraction approval"
                    continue
                ok, reason = url_exists(row["url"])
                if not ok:
                    raise RuntimeError(reason)
                download(row["url"], raw_dir / row["filename"])
                row["local_path"] = str(raw_dir / row["filename"])
                row["sha256"] = sha256_file(raw_dir / row["filename"])
            except Exception as exc:
                row["download_decision"] = "failed"
                row["decision_reason"] = f"download failed: {exc}"
                warnings.append(f"{row['filename']}: {exc}")
    pd.DataFrame(inventory).to_csv(out_dir / "supplementary_file_inventory.tsv", sep="\t", index=False)

    groups: dict[str, dict] = defaultdict(dict)
    for row in inventory:
        name = row["filename"]
        sample_key = re.sub(r"_(barcodes|features|matrix).*", "", name)
        if "matrix.mtx" in name:
            groups[sample_key]["matrix"] = row.get("local_path") or str(raw_dir / name)
        elif "barcodes.tsv" in name:
            groups[sample_key]["barcodes"] = row.get("local_path") or str(raw_dir / name)
        elif "features.tsv" in name:
            groups[sample_key]["features"] = row.get("local_path") or str(raw_dir / name)
        elif "GEO_Metadata" in name:
            groups[sample_key]["metadata"] = name

    qc_rows, marker_rows, key_rows = [], [], []
    for group in groups.values():
        if {"matrix", "barcodes", "features"}.issubset(group) and all(Path(group[k]).exists() for k in ("matrix", "barcodes", "features")):
            try:
                local_group = {key: Path(value).name for key, value in group.items()}
                local_raw_dir = Path(group["matrix"]).parent
                qc, markers, key = analyze_sample(local_group, local_raw_dir)
                qc_rows.append(qc)
                marker_rows.extend(markers)
                key_rows.extend(key)
            except Exception as exc:
                warnings.append(f"sample analysis failed for {group.get('matrix')}: {exc}")

    bcr_rows = [analyze_bcr(Path(row["local_path"])) for row in inventory if row["file_type"] == "vdj_contig" and row.get("local_path") and Path(row["local_path"]).exists()]
    pd.DataFrame(qc_rows, columns=["patient_id", "sample_id", "tissue_type", "tumor_or_tdln", "platform", "estimated_cells", "detected_gene_count", "nFeature_median", "nCount_median", "percent_mt_median", "doublet_estimate", "low_quality_cell_fraction", "source_file"]).to_csv(out_dir / "sample_qc_summary.tsv", sep="\t", index=False)
    pd.DataFrame(marker_rows, columns=["patient_id", "sample_id", "tissue_type", "tumor_or_tdln", "celltype_or_marker_group", "mean_marker_score", "cell_count_assigned"]).to_csv(out_dir / "celltype_marker_summary.tsv", sep="\t", index=False)
    pd.DataFrame(key_rows, columns=["patient_id", "sample_id", "tissue_type", "tumor_or_tdln", "celltype", "gene", "mean_expression", "detection_rate"]).to_csv(out_dir / "key_gene_expression_by_tissue.tsv", sep="\t", index=False)
    pd.DataFrame(key_rows, columns=["patient_id", "sample_id", "tissue_type", "tumor_or_tdln", "celltype", "gene", "mean_expression", "detection_rate"]).to_csv(out_dir / "key_gene_expression_by_celltype.tsv", sep="\t", index=False)
    pd.DataFrame(key_rows, columns=["patient_id", "sample_id", "tissue_type", "tumor_or_tdln", "celltype", "gene", "mean_expression", "detection_rate"]).to_csv(out_dir / "key_gene_expression_by_patient.tsv", sep="\t", index=False)
    pd.DataFrame(bcr_rows, columns=["patient_id", "sample_id", "tissue_type", "tumor_or_tdln", "valid_clonotype_count", "expanded_clonotype_count", "shannon", "gini", "status"]).to_csv(out_dir / "bcr_basic_summary.tsv", sep="\t", index=False)

    manifest_rows = []
    for row in qc_rows:
        manifest_rows.append(
            {
                "patient_id": row["patient_id"],
                "sample_id": row["sample_id"],
                "tissue_type": row["tissue_type"],
                "tumor_or_tdln": row["tumor_or_tdln"],
                "gex_library": "yes",
                "vdj_library": "unknown",
                "platform": row["platform"],
                "paired_status": "patient-level inferred",
                "source_file": row["source_file"],
                "estimated_cells": row["estimated_cells"],
            }
        )
    if not manifest_rows:
        by_sample = {}
        for row in inventory:
            parsed = sample_from_name(row["filename"])
            if parsed["sample_id"]:
                item = by_sample.setdefault(
                    parsed["sample_id"],
                    {
                        "patient_id": parsed["patient_id"],
                        "sample_id": parsed["sample_id"],
                        "tissue_type": parsed["tissue_type"],
                        "tumor_or_tdln": parsed["tumor_or_tdln"],
                        "gex_library": "no",
                        "vdj_library": "no",
                        "platform": "10x Genomics",
                        "paired_status": "inferred_from_filename_pending_metadata",
                        "estimated_cells": "",
                        "source_file": [],
                    },
                )
                if row["required_for_gex"]:
                    item["gex_library"] = "yes"
                if row["required_for_bcr"]:
                    item["vdj_library"] = "yes"
                item["source_file"].append(row["filename"])
        for item in by_sample.values():
            item["source_file"] = ";".join(sorted(set(item["source_file"])))
            manifest_rows.append(item)
    else:
        for row in manifest_rows:
            row["tumor_or_tdln"] = row.pop("tumor_or_tdln")
    manifest_rows = list({row["sample_id"]: row for row in manifest_rows}.values())
    pd.DataFrame(manifest_rows, columns=["patient_id", "sample_id", "tissue_type", "tumor_or_tdln", "gex_library", "vdj_library", "platform", "paired_status", "estimated_cells", "source_file"]).to_csv(out_dir / "sample_manifest.tsv", sep="\t", index=False)

    attempted_downloads = [row for row in inventory if row["decision_reason"].startswith("download failed")]
    blocked_members = [row for row in inventory if row["download_decision"] == "blocked"]
    status = "COMPLETED" if qc_rows else "BLOCKED" if attempted_downloads or blocked_members else "METADATA_ONLY"
    if not qc_rows:
        (out_dir / "NOT_RUN_reason.txt").write_text(
            "No complete processed matrix/barcode/features groups were parsed. GEO exposes an archive-only layout: processed members are listed in filelist.txt but require RAW.tar extraction. RAW.tar was not downloaded because this run does not approve default RAW.tar download. No formal expression plots were generated.\n",
            encoding="utf-8",
        )
    main_axis = "NO"
    branch_value = "B-cell / tumor-draining lymph-node immune niche"
    if key_rows:
        key_df = pd.DataFrame(key_rows)
        spp1 = pd.to_numeric(key_df.loc[key_df["gene"] == "SPP1", "detection_rate"], errors="coerce").max()
        epithelial_cells = sum(row.get("cell_count_assigned", 0) for row in marker_rows if row.get("celltype_or_marker_group") == "malignant_epithelial")
        if pd.notna(spp1) and spp1 > 0.05 and epithelial_cells >= 100:
            main_axis = "MAYBE"
    axis_status = "NOT_TESTED" if not key_rows else "INSUFFICIENT_DATA"
    axis_rows = [
        {"axis": "SPP1-CD44/ITGB1", "patient_id": "", "support_status": axis_status, "support_reason": "Processed matrix unavailable or insufficient for patient-level validation."},
        {"axis": "CD209-C1Q-myeloid niche", "patient_id": "", "support_status": axis_status, "support_reason": "Requires parsed celltype-level expression and patient-level comparison."},
    ]
    pd.DataFrame(axis_rows).to_csv(out_dir / "candidate_axis_patient_support.tsv", sep="\t", index=False)
    (out_dir / "candidate_axis_summary.md").write_text(
        "\n".join(
            [
                "# GSE319733 Candidate Axis Summary",
                "",
                f"- analysis_status: {status}",
                f"- SPP1-CD44/ITGB1: {axis_status}",
                f"- CD209/SPP1/C1Q/CD44/ITGB1/MMP14: {axis_status}",
                "- reason: patient-level matrix evidence is required before support can be claimed.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    summary = [
        "# GSE319733 Real Analysis Summary",
        "",
        f"- analysis_status: {status}",
        f"- samples_with_GEX_parsed: {len(qc_rows)}",
        f"- BCR_contig_files_parsed: {len(bcr_rows)}",
        "- RAW.tar downloaded: no",
        "- blocking_reason: processed files require RAW.tar extraction, which is not approved in this run",
        f"- main_axis_eligibility: {main_axis}",
        f"- branch_value: {branch_value}",
        f"- warnings: {len(warnings)}",
        "",
        "## Interpretation",
        "Processed GEX/VDJ files were downloaded individually from the GEO supplementary listing when available. RAW.tar and FASTQ-style raw sequencing files were not downloaded.",
        "Candidate axes remain exploratory and require patient-level/pseudobulk confirmation before use as primary target evidence.",
    ]
    (out_dir / "GSE319733_initial_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    gate = evaluate_quality_gate(
        required_outputs=[str(out_dir / "supplementary_file_inventory.tsv"), str(out_dir / "sample_manifest.tsv"), str(out_dir / "NOT_RUN_reason.txt") if not qc_rows else str(out_dir / "sample_qc_summary.tsv")],
        required_nonempty_outputs=[str(out_dir / "sample_qc_summary.tsv")] if qc_rows else [],
    )
    write_status(out_dir / "status.json", "GSE319733_analysis", status, run_id=args.run_id, warnings=warnings, errors=errors, outputs=[str(p) for p in out_dir.glob("*")], archive_only_layout_detected=archive_only_layout, direct_member_download_attempts=0 if archive_only_layout else len(attempted_downloads), **gate)
    write_status(out_dir / "analysis_status.json", "GSE319733_analysis", status, run_id=args.run_id, warnings=warnings, errors=errors, outputs=[str(p) for p in out_dir.glob("*")], archive_only_layout_detected=archive_only_layout, direct_member_download_attempts=0 if archive_only_layout else len(attempted_downloads), **gate)
    print(out_dir)


if __name__ == "__main__":
    main()
