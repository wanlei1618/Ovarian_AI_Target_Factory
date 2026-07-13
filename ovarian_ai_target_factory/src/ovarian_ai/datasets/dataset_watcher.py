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
            }
        )
    return records


CURATED_DAILY_DATASETS = {
    "GSE319733": {
        "dataset_id": "GSE319733",
        "title": "Tumor-draining lymph nodes in ovarian cancer lack germinal centers but harbor tumor-reactive memory B cells clonally linked to intra-tumoral B cells",
        "disease": "ovarian cancer",
        "modality": "single-cell RNA-seq / BCR",
        "platform": "10x Genomics",
        "sample_count": "20",
        "download_url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE319733",
        "priority_score": "9",
        "recommended_action": "Approved for metadata and small-file/lightweight parsing only.",
        "dataset_action": "approve_download",
        "action_reason": "high-priority ovarian cancer single-cell RNA-seq/BCR dataset involving tumor-draining lymph nodes and matched primary tumors; suitable for immune niche branch analysis",
        "raw_file_size_estimate": "unknown; RAW tar not downloaded by default",
        "modality_confidence": "high",
        "disease_relevance": "high",
        "main_project_relevance": "medium",
        "branch_project": "B-cell / tumor-draining lymph node immune niche in ovarian cancer",
        "approved_by_rule": "yes",
    },
    "GSE262172": {
        "dataset_id": "GSE262172",
        "title": "GSK-J4 treatment in ovarian cancer cell lines (ATAC-Seq)",
        "disease": "ovarian cancer",
        "modality": "ATAC-seq",
        "platform": "",
        "sample_count": "9",
        "download_url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE262172",
        "priority_score": "6",
        "recommended_action": "Metadata-only archive during MVP.",
        "dataset_action": "metadata_only",
        "action_reason": "ATAC-seq dataset in ovarian cancer cell lines; RAW file is relatively large and ATAC pipeline is not yet part of MVP; defer large download",
        "raw_file_size_estimate": "unknown; likely non-trivial ATAC-seq raw files",
        "modality_confidence": "high",
        "disease_relevance": "medium",
        "main_project_relevance": "low",
        "branch_project": "chromatin accessibility and epigenetic drug response",
        "approved_by_rule": "no",
    },
    "GSE310580": {
        "dataset_id": "GSE310580",
        "title": "DNA Methylation Profiling Enables Subclassification of Mucinous Ovarian Carcinoma and Distinguishes It from Extraovarian Mucinous Metastases",
        "disease": "ovarian cancer",
        "modality": "methylation",
        "platform": "",
        "sample_count": "162",
        "download_url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE310580",
        "priority_score": "3",
        "recommended_action": "Metadata-only archive during MVP.",
        "dataset_action": "metadata_only",
        "action_reason": "mucinous ovarian carcinoma methylation classifier dataset; useful as a diagnostic ML branch but not primary HGSOC target discovery workflow",
        "raw_file_size_estimate": "unknown; no raw download approved",
        "modality_confidence": "high",
        "disease_relevance": "medium",
        "main_project_relevance": "low",
        "branch_project": "mucinous ovarian carcinoma methylation classification",
        "approved_by_rule": "no",
    },
}


def refine_dataset_record(record: dict) -> dict:
    accession = record.get("dataset_id", "")
    if accession in CURATED_DAILY_DATASETS:
        refined = dict(CURATED_DAILY_DATASETS[accession])
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
        }
    )
    return refined


def ensure_curated_daily_records(records: list[dict]) -> list[dict]:
    by_id = {record.get("dataset_id", ""): record for record in records}
    for accession, record in CURATED_DAILY_DATASETS.items():
        by_id.setdefault(accession, record)
    ordered = []
    for accession in ("GSE319733", "GSE262172", "GSE310580"):
        if accession in by_id:
            ordered.append(by_id.pop(accession))
    ordered.extend(by_id.values())
    return ordered


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
    terms = read_search_terms(config_path)
    query = build_geo_query(terms)
    logger.info("Starting GEO dataset search with retmax=%s", retmax)
    logger.info("GEO query: %s", query)

    if dry_run:
        return report_dir

    records = ensure_curated_daily_records(fetch_geo_records(query, retmax, logger))
    refined_records = [refine_dataset_record(record) for record in records]
    out_path = report_dir / f"new_dataset_registry_{yyyymmdd(selected_date)}.tsv"
    refined_path = report_dir / f"refined_dataset_registry_{yyyymmdd(selected_date)}.tsv"
    audit_path = report_dir / f"dataset_action_audit_{yyyymmdd(selected_date)}.md"
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS[:9], delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    with refined_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(refined_records)
    write_dataset_action_audit(refined_records, audit_path, selected_date)
    logger.info("Wrote %s GEO records to %s", len(records), out_path)
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
