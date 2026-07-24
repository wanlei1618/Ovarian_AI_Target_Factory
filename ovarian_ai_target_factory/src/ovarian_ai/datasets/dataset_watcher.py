from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import yaml

from ovarian_ai.utils.paths import assert_not_c_data_path, daily_reports_root


FIELDS = [
    "dataset_id",
    "title",
    "disease",
    "modality",
    "platform",
    "sample_count",
    "download_url",
    "priority_score",
    "recommended_action",
    "dataset_action",
    "action_reason",
    "raw_file_size_estimate",
    "modality_confidence",
    "disease_relevance",
    "main_project_relevance",
    "branch_project",
    "approved_by_rule",
    "source_type",
    "analysis_status",
    "evidence_level",
    "ovarian_data_used",
    "hgsoc_specific",
    "public_data_accession",
    "public_data_verified",
    "public_code_url",
    "public_code_verified",
    "independent_validation",
    "functional_perturbation",
    "single_cell_validation",
    "spatial_validation",
    "depmap_validation",
    "drug_response_validation",
]


NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def yyyymmdd(value: str) -> str:
    return value.replace("-", "")


def setup_logger(outdir: Path, run_date: str) -> logging.Logger:
    logger = logging.getLogger("dataset_watcher")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.FileHandler(outdir / "logs" / f"dataset_watcher_{yyyymmdd(run_date)}.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def read_search_terms(config_path: Path) -> dict:
    path = config_path.parent / "search_terms.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def build_geo_query(terms: dict) -> str:
    disease_terms = terms.get("disease") or ["ovarian cancer"]
    omics_terms = terms.get("omics") or ["RNA-seq", "single-cell RNA-seq", "spatial transcriptomics"]
    disease_query = " OR ".join(f'"{term}"' for term in disease_terms[:6])
    omics_query = " OR ".join(f'"{term}"' for term in omics_terms[:10])
    return f"({disease_query}) AND ({omics_query}) AND gse[ETYP]"


def fetch_text(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "OvarianAITargetFactory/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def geo_search(query: str, retmax: int, logger: logging.Logger) -> list[str]:
    params = urllib.parse.urlencode(
        {
            "db": "gds",
            "term": query,
            "retmode": "json",
            "retmax": str(retmax),
            "sort": "date",
        }
    )
    url = f"{NCBI_BASE}/esearch.fcgi?{params}"
    try:
        payload = json.loads(fetch_text(url))
        return payload.get("esearchresult", {}).get("idlist", [])
    except Exception as exc:
        logger.exception("GEO esearch failed: %s", exc)
        return []


def geo_summary(ids: list[str], logger: logging.Logger) -> dict:
    if not ids:
        return {}
    params = urllib.parse.urlencode({"db": "gds", "id": ",".join(ids), "retmode": "json"})
    url = f"{NCBI_BASE}/esummary.fcgi?{params}"
    try:
        payload = json.loads(fetch_text(url))
        return payload.get("result", {})
    except Exception as exc:
        logger.exception("GEO esummary failed: %s", exc)
        return {}


def infer_modality(text: str) -> str:
    lowered = text.lower()
    if "atac" in lowered or "chromatin accessibility" in lowered:
        return "ATAC-seq"
    if "spatial" in lowered or "visium" in lowered or "geomx" in lowered:
        return "spatial transcriptomics"
    if "single-cell" in lowered or "single cell" in lowered or "scrna" in lowered:
        return "single-cell RNA-seq"
    if "rna-seq" in lowered or "transcript" in lowered or "expression" in lowered:
        return "bulk transcriptomics"
    if "methyl" in lowered:
        return "methylation"
    return "unknown"


def priority_score(record: dict) -> int:
    text = " ".join(str(record.get(key, "")) for key in ("title", "summary", "gdsType", "taxon"))
    lowered = text.lower()
    score = 0
    if "ovarian" in lowered:
        score += 3
    if any(token in lowered for token in ("single-cell", "single cell", "scrna")):
        score += 2
    if any(token in lowered for token in ("spatial", "visium", "geomx")):
        score += 2
    if any(token in lowered for token in ("survival", "response", "resistance", "platinum", "parp", "recurrent")):
        score += 3
    if any(token in lowered for token in ("rna-seq", "expression", "transcript")):
        score += 1
    return score


def parse_sample_count(record: dict) -> str:
    for key in ("n_samples", "samples", "sample_count"):
        value = record.get(key)
        if value:
            return str(value)
    summary = str(record.get("summary", ""))
    match = re.search(r"(\d+)\s+samples?", summary, flags=re.IGNORECASE)
    return match.group(1) if match else ""


def fetch_geo_records(query: str, retmax: int, logger: logging.Logger) -> list[dict]:
    ids = geo_search(query, retmax, logger)
    summary = geo_summary(ids, logger)
    records = []
    for uid in summary.get("uids", []):
        item = summary.get(uid, {})
        accession = item.get("accession") or item.get("gse") or uid
        title = item.get("title", "")
        source = " ".join(item.get("GPL", []) if isinstance(item.get("GPL"), list) else [])
        text = f"{title} {item.get('summary', '')} {source}"
        score = priority_score(item)
        records.append(
            {
                "dataset_id": accession,
                "title": title,
                "disease": "ovarian cancer" if "ovarian" in text.lower() else "",
                "modality": infer_modality(text),
                "platform": source or item.get("gdsType", ""),
                "sample_count": parse_sample_count(item),
                "download_url": f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={accession}",
                "priority_score": str(score),
                "recommended_action": "Review metadata first; do not download matrix files until approved.",
                "source_type": "auto_geo_search",
            }
        )
    return records


CURATED_DAILY_DATASETS: dict[str, dict] = {}


def load_curated_datasets(config_path: Path) -> list[dict]:
    path = config_path.parent / "curated_datasets.yaml"
    if not path.exists():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = payload.get("datasets") or []
    return [dict(row) for row in rows if row.get("dataset_id")]


def refine_dataset_record(record: dict, curated_by_id: dict[str, dict] | None = None) -> dict:
    curated_by_id = curated_by_id if curated_by_id is not None else CURATED_DAILY_DATASETS
    accession = record.get("dataset_id", "")
    if accession in curated_by_id:
        refined = dict(curated_by_id[accession])
        for key, value in record.items():
            if value and key not in {
                "dataset_action",
                "action_reason",
                "raw_file_size_estimate",
                "modality_confidence",
                "disease_relevance",
                "main_project_relevance",
                "branch_project",
                "approved_by_rule",
            }:
                refined[key] = value
        return refined

    text = f"{record.get('title', '')} {record.get('modality', '')}".lower()
    action = "needs_manual_review"
    reason = "No curated action rule matched; review metadata before any download."
    main_relevance = "medium" if "ovarian" in text else "low"
    if "spatial" in text or "single-cell" in text or "single cell" in text:
        action = "defer"
        reason = "Potentially useful high-dimensional dataset; defer until size and metadata are reviewed."
    refined = dict(record)
    refined.update(
        {
            "dataset_action": action,
            "action_reason": reason,
            "raw_file_size_estimate": "unknown",
            "modality_confidence": "medium" if record.get("modality") != "unknown" else "low",
            "disease_relevance": "medium" if "ovarian" in text else "unknown",
            "main_project_relevance": main_relevance,
            "branch_project": "",
            "approved_by_rule": "no",
            "source_type": record.get("source_type", "auto_geo_search"),
            "analysis_status": "METADATA_ONLY",
            "evidence_level": "limited" if "ovarian" in text else "weak",
            "ovarian_data_used": "yes" if "ovarian" in text else "unknown",
            "hgsoc_specific": "yes" if "hgsoc" in text or "high-grade serous" in text else "unknown",
            "public_data_accession": accession,
            "public_data_verified": "yes" if accession.startswith("GSE") else "unknown",
            "public_code_url": "",
            "public_code_verified": "no",
            "independent_validation": "unknown",
            "functional_perturbation": "yes" if "crispr" in text or "knock" in text else "unknown",
            "single_cell_validation": "yes" if "single-cell" in text or "single cell" in text else "no",
            "spatial_validation": "yes" if "spatial" in text else "no",
            "depmap_validation": "yes" if "depmap" in text else "no",
            "drug_response_validation": "yes" if "drug" in text or "resistance" in text else "unknown",
        }
    )
    return refined


def curated_records() -> list[dict]:
    return [dict(CURATED_DAILY_DATASETS[key]) for key in sorted(CURATED_DAILY_DATASETS)]


def newly_detected_records(records: list[dict], curated_ids: set[str] | None = None) -> list[dict]:
    curated_ids = curated_ids if curated_ids is not None else set(CURATED_DAILY_DATASETS)
    return [record for record in records if record.get("dataset_id") not in curated_ids]


def update_dataset_history(history_path: Path, records: list[dict], run_date: str) -> list[dict]:
    history = {}
    if history_path.exists():
        with history_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                history[row["dataset_id"]] = dict(row)
    for record in records:
        dataset_id = record.get("dataset_id", "")
        if not dataset_id:
            continue
        previous = history.get(dataset_id)
        times_seen = int(previous.get("times_seen", "0")) + 1 if previous else 1
        history[dataset_id] = {
            "dataset_id": dataset_id,
            "first_seen_date": previous.get("first_seen_date", run_date) if previous else run_date,
            "last_seen_date": run_date,
            "times_seen": str(times_seen),
            "source": record.get("source_type", ""),
            "latest_title": record.get("title", ""),
            "latest_modality": record.get("modality", ""),
            "latest_action": record.get("dataset_action", record.get("recommended_action", "")),
        }
    return sorted(history.values(), key=lambda item: item["dataset_id"])


def write_dataset_action_audit(records: list[dict], path: Path, run_date: str) -> None:
    def section(title: str, action_values: set[str]) -> list[str]:
        selected = [record for record in records if record.get("dataset_action") in action_values]
        lines = [f"## {title}"]
        if not selected:
            return lines + ["- None", ""]
        for record in selected:
            lines.extend(
                [
                    f"- {record.get('dataset_id')}: {record.get('title')}",
                    f"  - dataset_action: {record.get('dataset_action')}",
                    f"  - action_reason: {record.get('action_reason')}",
                    f"  - branch_project: {record.get('branch_project')}",
                ]
            )
        return lines + [""]

    lines = [f"# Dataset Action Audit: {run_date}", ""]
    lines += section("Approved downloads", {"approve_download"})
    lines += section("Metadata-only datasets", {"metadata_only"})
    lines += section("Deferred downloads", {"defer", "needs_manual_review"})
    lines += section("Excluded datasets", {"exclude"})
    path.write_text("\n".join(lines), encoding="utf-8")


def run(
    run_date: str | None = None,
    config: Path | None = None,
    outdir: Path | None = None,
    dry_run: bool = False,
    retmax: int = 20,
) -> Path:
    selected_date = run_date or date.today().isoformat()
    report_dir = outdir or daily_reports_root(config)
    assert_not_c_data_path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "logs").mkdir(parents=True, exist_ok=True)
    logger = setup_logger(report_dir, selected_date)
    config_path = config or Path("config/paths.yaml")
    global CURATED_DAILY_DATASETS
    curated = load_curated_datasets(config_path)
    CURATED_DAILY_DATASETS = {record["dataset_id"]: record for record in curated}
    terms = read_search_terms(config_path)
    query = build_geo_query(terms)
    logger.info("Starting GEO dataset search with retmax=%s", retmax)
    logger.info("GEO query: %s", query)

    if dry_run:
        return report_dir

    raw_records = fetch_geo_records(query, retmax, logger)
    history_path = report_dir / "dataset_history.tsv"
    existing_history = {}
    if history_path.exists():
        with history_path.open("r", encoding="utf-8", newline="") as handle:
            existing_history = {row.get("dataset_id", ""): row for row in csv.DictReader(handle, delimiter="\t")}
    new_records = [
        record
        for record in newly_detected_records(raw_records, set(CURATED_DAILY_DATASETS))
        if record.get("dataset_id") not in existing_history
    ]
    combined_by_id = {record.get("dataset_id", ""): record for record in raw_records}
    for record in curated:
        combined_by_id[record["dataset_id"]] = record
    refined_records = [refine_dataset_record(record, CURATED_DAILY_DATASETS) for record in combined_by_id.values()]
    history_rows = update_dataset_history(history_path, refined_records, selected_date)
    out_path = report_dir / f"new_dataset_registry_{yyyymmdd(selected_date)}.tsv"
    raw_path = report_dir / f"raw_geo_hits_{yyyymmdd(selected_date)}.tsv"
    newly_path = report_dir / f"daily_newly_detected_datasets_{yyyymmdd(selected_date)}.tsv"
    curated_path = report_dir / "curated_dataset_registry.tsv"
    refined_path = report_dir / f"refined_dataset_registry_{yyyymmdd(selected_date)}.tsv"
    audit_path = report_dir / f"dataset_action_audit_{yyyymmdd(selected_date)}.md"
    for path, rows, fields in (
        (raw_path, raw_records, FIELDS[:18]),
        (newly_path, new_records, FIELDS[:18]),
        (out_path, new_records, FIELDS[:9]),
        (curated_path, curated, FIELDS),
    ):
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    with refined_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(refined_records)
    with history_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["dataset_id", "first_seen_date", "last_seen_date", "times_seen", "source", "latest_title", "latest_modality", "latest_action"],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(history_rows)
    write_dataset_action_audit(refined_records, audit_path, selected_date)
    logger.info("Wrote %s raw GEO records to %s", len(raw_records), raw_path)
    logger.info("Wrote %s newly detected GEO records to %s", len(new_records), newly_path)
    logger.info("Wrote refined dataset action audit to %s", audit_path)
    return report_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate MVP v0.1 GEO dataset registry.")
    parser.add_argument("--date", dest="run_date")
    parser.add_argument("--config", type=Path, default=Path("config/paths.yaml"))
    parser.add_argument("--outdir", type=Path)
    parser.add_argument("--retmax", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    outdir = run(args.run_date, args.config, args.outdir, args.dry_run, args.retmax)
    print(f"dataset_watcher output: {outdir}")


if __name__ == "__main__":
    main()
