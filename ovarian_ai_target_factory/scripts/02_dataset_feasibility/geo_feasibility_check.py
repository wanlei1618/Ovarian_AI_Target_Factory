from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.utils.paths import ensure_subdirs
from ovarian_ai.utils.run_status import write_status


NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str]]) -> None:
        if tag != "a":
            return
        for key, value in attrs:
            if key == "href":
                self.links.append(value)


def fetch_text(url: str, timeout: int = 45) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "OvarianAITargetFactory/feasibility"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def geo_uid(accession: str) -> str:
    params = urllib.parse.urlencode({"db": "gds", "term": f"{accession}[ACCN]", "retmode": "json", "retmax": "1"})
    payload = json.loads(fetch_text(f"{NCBI_BASE}/esearch.fcgi?{params}"))
    ids = payload.get("esearchresult", {}).get("idlist", [])
    return ids[0] if ids else ""


def geo_summary(accession: str) -> dict:
    uid = geo_uid(accession)
    if not uid:
        return {}
    params = urllib.parse.urlencode({"db": "gds", "id": uid, "retmode": "json"})
    payload = json.loads(fetch_text(f"{NCBI_BASE}/esummary.fcgi?{params}"))
    return payload.get("result", {}).get(uid, {})


def suppl_url(accession: str) -> str:
    prefix = accession[:6] + "nnn"
    return f"https://ftp.ncbi.nlm.nih.gov/geo/series/{prefix}/{accession}/suppl/"


def matrix_url(accession: str) -> str:
    prefix = accession[:6] + "nnn"
    return f"https://ftp.ncbi.nlm.nih.gov/geo/series/{prefix}/{accession}/matrix/{accession}_series_matrix.txt.gz"


def head_size(url: str) -> tuple[int, str]:
    try:
        request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "OvarianAITargetFactory/feasibility"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return int(response.headers.get("Content-Length") or 0), ""
    except Exception as exc:
        return 0, str(exc)


def list_supplementary(accession: str) -> list[dict]:
    base = suppl_url(accession)
    try:
        html = fetch_text(base)
    except Exception as exc:
        return [{"filename": "", "url": base, "size_bytes": 0, "file_type": "listing_error", "download_decision": "metadata_only", "decision_reason": str(exc)}]
    parser = LinkParser()
    parser.feed(html)
    rows = []
    for link in parser.links:
        if link.startswith("?") or link.startswith("/") or link == "../":
            continue
        name = urllib.parse.unquote(link)
        url = base + link
        size, err = head_size(url)
        lower = name.lower()
        if lower.endswith((".fastq.gz", ".fq.gz", ".bam", ".tar")):
            decision = "skip"
            reason = "raw sequencing/archive file is not downloaded by default"
        elif lower.endswith((".gz", ".txt", ".tsv", ".csv", ".mtx")) and size and size < 5 * 1024**3:
            decision = "inspect_processed_files"
            reason = "processed or metadata-sized file can be inspected if needed"
        else:
            decision = "metadata_only"
            reason = err or "unknown file type or size"
        rows.append(
            {
                "filename": name,
                "url": url,
                "size_bytes": size,
                "file_type": lower.rsplit(".", 1)[-1] if "." in lower else "unknown",
                "download_decision": decision,
                "decision_reason": reason,
            }
        )
    return rows


def write_gse337706(out_dir: Path, summary: dict, inventory: list[dict]) -> None:
    text = " ".join(str(summary.get(key, "")) for key in ("title", "summary", "gdsType"))
    lower = text.lower()
    disease_rows = [
        {"disease_group": "ovarian subgroup", "status": "present" if "ovarian" in lower else "requires_manual_metadata_review"},
        {"disease_group": "HGSOC subgroup", "status": "present" if "hgsoc" in lower or "high-grade serous" in lower else "not_confirmed_from_summary"},
        {"disease_group": "benign gynecologic controls", "status": "present" if "benign" in lower else "not_confirmed_from_summary"},
        {"disease_group": "other cancer controls", "status": "present" if "cancer" in lower and "ovarian" in lower else "not_confirmed_from_summary"},
    ]
    with (out_dir / "disease_group_counts.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["disease_group", "status"], delimiter="\t")
        writer.writeheader()
        writer.writerows(disease_rows)
    with (out_dir / "donor_manifest.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["donor_id", "disease_group", "source", "metadata_confidence"], delimiter="\t")
        writer.writeheader()
    (out_dir / "analysis_feasibility.md").write_text(
        "\n".join(
            [
                "# GSE337706 Analysis Feasibility",
                "",
                "- branch_project: ovarian liquid biopsy / platelet-coated CTC",
                "- main_project_relevance: medium-low",
                "- disease_relevance: high for ovarian subgroup",
                "- dataset_action: inspect_processed_files",
                "- not_for: CNV subclone validation or direct SPP1-CD44/ITGB1 main-axis validation",
                f"- title: {summary.get('title', '')}",
                f"- supplementary_files: {len(inventory)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_gse338829(out_dir: Path, summary: dict, inventory: list[dict]) -> None:
    text = " ".join(str(summary.get(key, "")) for key in ("title", "summary", "gdsType"))
    lower = text.lower()
    perturbation = ("rbms1" in lower and "nedd4" in lower) or "knock" in lower or "sirna" in lower
    decision = {
        "accession": "GSE338829",
        "branch_project": "RBMS1-NEDD4 perturbation validation",
        "main_project_relevance": "low",
        "dataset_action": "download_processed_counts_only" if perturbation else "metadata_only",
        "evidence_type": "functional_perturbation" if perturbation else "metadata_uncertain",
        "raw_download_allowed": False,
        "decision_reason": "Metadata supports perturbation RNA-seq review." if perturbation else "Summary did not fully confirm RBMS1/NEDD4 perturbation design.",
    }
    (out_dir / "GSE338829_metadata_summary.md").write_text(
        "\n".join(["# GSE338829 Metadata Summary", "", f"- title: {summary.get('title', '')}", f"- summary: {summary.get('summary', '')}", f"- supplementary_files: {len(inventory)}"]) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "GSE338829_sample_design.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample_id", "cell_line", "condition", "replicate", "metadata_confidence"], delimiter="\t")
        writer.writeheader()
    (out_dir / "GSE338829_download_decision.json").write_text(json.dumps(decision, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "paths.yaml")
    args = parser.parse_args()
    dirs = ensure_subdirs(args.config)
    out_root = dirs["results"] / "dataset_feasibility" / args.run_id
    out_root.mkdir(parents=True, exist_ok=True)
    statuses = {}
    for accession in ("GSE337706", "GSE338829"):
        out_dir = out_root / accession
        out_dir.mkdir(parents=True, exist_ok=True)
        errors = []
        try:
            summary = geo_summary(accession)
            inventory = list_supplementary(accession)
        except Exception as exc:
            summary = {}
            inventory = []
            errors.append(str(exc))
        with (out_dir / "supplementary_file_inventory.tsv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["filename", "url", "size_bytes", "file_type", "download_decision", "decision_reason"], delimiter="\t")
            writer.writeheader()
            writer.writerows(inventory)
        if accession == "GSE337706":
            write_gse337706(out_dir, summary, inventory)
        else:
            write_gse338829(out_dir, summary, inventory)
        status = "COMPLETED_WITH_WARNINGS" if errors else "COMPLETED"
        write_status(out_dir / "status.json", f"{accession}_feasibility", status, run_id=args.run_id, errors=errors, outputs=[str(p) for p in out_dir.glob("*")])
        statuses[accession] = status
    write_status(out_root / "status.json", "dataset_feasibility", "COMPLETED_WITH_WARNINGS" if any(v != "COMPLETED" for v in statuses.values()) else "COMPLETED", run_id=args.run_id, dataset_status=statuses)
    print(out_root)


if __name__ == "__main__":
    main()
