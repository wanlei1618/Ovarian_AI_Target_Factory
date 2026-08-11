from __future__ import annotations

import argparse
import csv
import gzip
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
from ovarian_ai.utils.run_status import evaluate_quality_gate, write_status


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
    if not ids:
        return ""
    params = urllib.parse.urlencode({"db": "gds", "id": ",".join(ids), "retmode": "json"})
    summary = json.loads(fetch_text(f"{NCBI_BASE}/esummary.fcgi?{params}")).get("result", {})
    for uid in summary.get("uids", []):
        if summary.get(uid, {}).get("accession") == accession:
            return uid
    return ids[0]


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


def fetch_series_matrix(accession: str) -> dict[str, list[str]]:
    url = matrix_url(accession)
    request = urllib.request.Request(url, headers={"User-Agent": "OvarianAITargetFactory/feasibility"})
    with urllib.request.urlopen(request, timeout=60) as response:
        text = gzip.decompress(response.read()).decode("utf-8", errors="replace")
    fields: dict[str, list[str]] = {}
    for line in text.splitlines():
        if not line.startswith("!Sample_"):
            continue
        parts = [part.strip().strip('"') for part in line.split("\t")]
        fields[parts[0]] = parts[1:]
    return fields


def samples_from_matrix(accession: str) -> list[dict]:
    try:
        fields = fetch_series_matrix(accession)
    except Exception:
        fields = {}
    if not fields:
        params = urllib.parse.urlencode({"db": "gds", "term": f"{accession}[ACCN]", "retmode": "json", "retmax": "100"})
        payload = json.loads(fetch_text(f"{NCBI_BASE}/esearch.fcgi?{params}"))
        ids = payload.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        params = urllib.parse.urlencode({"db": "gds", "id": ",".join(ids), "retmode": "json"})
        summary = json.loads(fetch_text(f"{NCBI_BASE}/esummary.fcgi?{params}")).get("result", {})
        rows = []
        for uid in summary.get("uids", []):
            item = summary.get(uid, {})
            acc = item.get("accession", "")
            if not acc.startswith("GSM"):
                continue
            rows.append({"accession": accession, "sample_id": acc, "title": item.get("title", ""), "source_name": item.get("summary", ""), "characteristics": "", "donor_id": acc})
        return rows
    gsm = fields.get("!Sample_geo_accession", [])
    titles = fields.get("!Sample_title", [])
    source = fields.get("!Sample_source_name_ch1", [])
    characteristics = fields.get("!Sample_characteristics_ch1", [])
    rows = []
    for i, sample in enumerate(gsm):
        title = titles[i] if i < len(titles) else ""
        src = source[i] if i < len(source) else ""
        chars = characteristics[i] if i < len(characteristics) else ""
        text = f"{title} {src} {chars}"
        donor_match = re.search(r"(?:donor|patient|subject|P)[\s:_-]*(\d+)", text, flags=re.I)
        donor = f"D{donor_match.group(1)}" if donor_match else sample
        rows.append({"accession": accession, "sample_id": sample, "title": title, "source_name": src, "characteristics": chars, "donor_id": donor})
    return rows


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


def classify_disease(text: str) -> str:
    lower = text.lower()
    if "hgsoc" in lower or "high-grade serous" in lower:
        return "HGSOC"
    if "benign" in lower:
        return "benign gynecologic controls"
    if "healthy" in lower or "normal" in lower:
        return "healthy controls"
    if "ovarian" in lower:
        return "ovarian cancer"
    if "cancer" in lower or "carcinoma" in lower:
        return "other cancer controls"
    return "unknown"


def classify_ctc(text: str) -> str:
    lower = text.lower()
    if "platelet" in lower:
        return "platelet-coated CTC"
    if "naked" in lower:
        return "naked CTC"
    if "ctc" in lower or "circulating tumor" in lower:
        return "CTC unspecified"
    return "unknown"


def write_gse337706(out_dir: Path, summaries: dict[str, dict], inventories: dict[str, list[dict]], samples: list[dict]) -> str:
    combined = []
    for row in samples:
        text = f"{row.get('title','')} {row.get('source_name','')} {row.get('characteristics','')}"
        combined.append(
            {
                "accession": row["accession"],
                "sample_id": row["sample_id"],
                "donor_id": row["donor_id"],
                "title": row.get("title", ""),
                "disease_group": classify_disease(text),
                "ctc_group": classify_ctc(text),
                "platform": "GEO",
                "metadata_confidence": "medium" if row.get("title") else "low",
            }
        )
    donor_map = {}
    for row in combined:
        donor_map.setdefault(row["donor_id"], row)
    donor_rows = [
        {
            "donor_id": donor_id,
            "disease_group": row["disease_group"],
            "ctc_group": row["ctc_group"],
            "platform": row["platform"],
            "source": row["accession"],
            "metadata_confidence": row["metadata_confidence"],
        }
        for donor_id, row in sorted(donor_map.items())
    ]
    disease_counts = {}
    ctc_counts = {}
    for row in donor_rows:
        disease_counts[row["disease_group"]] = disease_counts.get(row["disease_group"], 0) + 1
        ctc_counts[row["ctc_group"]] = ctc_counts.get(row["ctc_group"], 0) + 1
    disease_rows = [{"disease_group": key, "donor_count": value} for key, value in sorted(disease_counts.items())]
    ctc_rows = [{"ctc_group": key, "donor_count": value} for key, value in sorted(ctc_counts.items())]
    with (out_dir / "combined_study_manifest.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["accession", "sample_id", "donor_id", "title", "disease_group", "ctc_group", "platform", "metadata_confidence"], delimiter="\t")
        writer.writeheader()
        writer.writerows(combined)
    with (out_dir / "donor_manifest.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["donor_id", "disease_group", "ctc_group", "platform", "source", "metadata_confidence"], delimiter="\t")
        writer.writeheader()
        writer.writerows(donor_rows)
    with (out_dir / "sample_platform_map.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample_id", "platform", "source"], delimiter="\t")
        writer.writeheader()
        writer.writerows([{"sample_id": row["sample_id"], "platform": row["platform"], "source": row["accession"]} for row in combined])
    with (out_dir / "disease_group_counts.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["disease_group", "donor_count"], delimiter="\t")
        writer.writeheader()
        writer.writerows(disease_rows)
    with (out_dir / "ctc_group_counts.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ctc_group", "donor_count"], delimiter="\t")
        writer.writeheader()
        writer.writerows(ctc_rows)
    with (out_dir / "processed_file_decision.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["accession", "filename", "download_decision", "decision_reason"], delimiter="\t")
        writer.writeheader()
        for accession, inventory in inventories.items():
            for item in inventory:
                writer.writerow({"accession": accession, "filename": item.get("filename", ""), "download_decision": item.get("download_decision", ""), "decision_reason": item.get("decision_reason", "")})
    status = "METADATA_ONLY" if donor_rows else "INSUFFICIENT_DATA"
    (out_dir / "analysis_feasibility.md").write_text(
        "\n".join(
            [
                "# GSE337705/GSE337706 Analysis Feasibility",
                "",
                "- branch_project: ovarian liquid biopsy / platelet-coated CTC",
                "- main_project_relevance: medium-low",
                "- disease_relevance: high for ovarian subgroup",
                "- dataset_action: inspect_processed_files",
                "- not_for: CNV subclone validation or direct SPP1-CD44/ITGB1 main-axis validation",
                f"- analysis_status: {status}",
                f"- donor_rows: {len(donor_rows)}",
                f"- supplementary_files: {sum(len(v) for v in inventories.values())}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return status


def write_gse338829(out_dir: Path, summary: dict, inventory: list[dict], samples: list[dict]) -> str:
    text = " ".join(str(summary.get(key, "")) for key in ("title", "summary", "gdsType"))
    text += " " + " ".join(f"{row.get('title','')} {row.get('source_name','')} {row.get('characteristics','')}" for row in samples)
    lower = text.lower()
    ripseq = "rip" in lower or "rna immunoprecip" in lower or "immunoprecipitation" in lower
    perturbation = (("rbms1" in lower and "nedd4" in lower) or "knock" in lower or "sirna" in lower) and not ripseq
    decision = {
        "accession": "GSE338829",
        "assay_type": "RIP-seq" if ripseq else "perturbation RNA-seq" if perturbation else "metadata_uncertain",
        "modality": "RIP-seq" if ripseq else "RNA-seq" if perturbation else "unknown",
        "branch_project": "RBMS1-NEDD4 RNA-binding target evidence" if ripseq else "RBMS1-NEDD4 perturbation validation",
        "main_project_relevance": "low",
        "dataset_action": "inspect_processed_files" if ripseq else "download_processed_counts_only" if perturbation else "metadata_only",
        "evidence_type": "RNA-binding target evidence" if ripseq else "functional_perturbation" if perturbation else "metadata_uncertain",
        "functional_perturbation": "supporting_from_paper_not_deposited_here" if ripseq else "yes" if perturbation else "unknown",
        "raw_download_allowed": False,
        "decision_reason": "Metadata indicates RIP-seq/RNA immunoprecipitation; do not treat as expression perturbation RNA-seq." if ripseq else "Metadata supports perturbation RNA-seq review." if perturbation else "Summary did not fully confirm RBMS1/NEDD4 perturbation design.",
        "sample_count": len(samples),
        "cell_line": ";".join(sorted({row.get("source_name", "") for row in samples if row.get("source_name")})),
    }
    (out_dir / "GSE338829_metadata_summary.md").write_text(
        "\n".join(["# GSE338829 Metadata Summary", "", f"- title: {summary.get('title', '')}", f"- summary: {summary.get('summary', '')}", f"- supplementary_files: {len(inventory)}"]) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "GSE338829_sample_design.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample_id", "cell_line", "condition", "ip_or_input", "replicate", "library_strategy", "metadata_confidence"], delimiter="\t")
        writer.writeheader()
        for idx, row in enumerate(samples, start=1):
            txt = f"{row.get('title','')} {row.get('source_name','')} {row.get('characteristics','')}"
            writer.writerow(
                {
                    "sample_id": row["sample_id"],
                    "cell_line": row.get("source_name", ""),
                    "condition": "RBMS1 antibody" if "rbms1" in txt.lower() else "control/input" if "input" in txt.lower() or "control" in txt.lower() else "unknown",
                    "ip_or_input": "IP" if "ip" in txt.lower() or "immunoprecip" in txt.lower() else "input" if "input" in txt.lower() else "unknown",
                    "replicate": str(idx),
                    "library_strategy": "RIP-seq" if ripseq else "RNA-seq" if perturbation else "unknown",
                    "metadata_confidence": "medium" if row.get("title") else "low",
                }
            )
    with (out_dir / "GSE338829_processed_file_decision.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["filename", "download_decision", "decision_reason"], delimiter="\t")
        writer.writeheader()
        writer.writerows([{"filename": item.get("filename", ""), "download_decision": item.get("download_decision", ""), "decision_reason": item.get("decision_reason", "")} for item in inventory])
    (out_dir / "GSE338829_download_decision.json").write_text(json.dumps(decision, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "GSE338829_assay_classification.json").write_text(json.dumps(decision, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "RBMS1_NEDD4_evidence_scope.md").write_text(
        "\n".join(
            [
                "# RBMS1/NEDD4 Evidence Scope",
                "",
                f"- assay_type: {decision['assay_type']}",
                f"- evidence_type: {decision['evidence_type']}",
                "- source_dataset: GSE338829",
                "- not_source_dataset: GSE319733",
                f"- decision_reason: {decision['decision_reason']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return "METADATA_ONLY" if samples else "INSUFFICIENT_DATA"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "paths.yaml")
    args = parser.parse_args()
    dirs = ensure_subdirs(args.config)
    out_root = dirs["results"] / "dataset_feasibility" / args.run_id
    out_root.mkdir(parents=True, exist_ok=True)
    statuses = {}
    joint_out = out_root / "GSE337705_GSE337706"
    joint_out.mkdir(parents=True, exist_ok=True)
    joint_summaries, joint_inventories, joint_samples, joint_errors = {}, {}, [], []
    for accession in ("GSE337705", "GSE337706"):
        try:
            joint_summaries[accession] = geo_summary(accession)
            joint_inventories[accession] = list_supplementary(accession)
            joint_samples.extend(samples_from_matrix(accession))
        except Exception as exc:
            joint_inventories[accession] = []
            joint_errors.append(f"{accession}: {exc}")
    with (joint_out / "supplementary_file_inventory.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["accession", "filename", "url", "size_bytes", "file_type", "download_decision", "decision_reason"], delimiter="\t")
        writer.writeheader()
        for accession, inventory in joint_inventories.items():
            for item in inventory:
                writer.writerow({"accession": accession, **item})
    joint_status = write_gse337706(joint_out, joint_summaries, joint_inventories, joint_samples)
    gate = evaluate_quality_gate([str(joint_out / "donor_manifest.tsv")], [str(joint_out / "donor_manifest.tsv")])
    if not gate["quality_gate_passed"]:
        joint_status = "INSUFFICIENT_DATA"
    write_status(joint_out / "status.json", "GSE337705_GSE337706_feasibility", joint_status, run_id=args.run_id, errors=joint_errors, **gate, outputs=[str(p) for p in joint_out.glob("*")])
    statuses["GSE337705_GSE337706"] = joint_status

    for accession in ("GSE338829",):
        out_dir = out_root / accession
        out_dir.mkdir(parents=True, exist_ok=True)
        errors = []
        try:
            summary = geo_summary(accession)
            inventory = list_supplementary(accession)
            samples = samples_from_matrix(accession)
        except Exception as exc:
            summary = {}
            inventory = []
            samples = []
            errors.append(str(exc))
        with (out_dir / "supplementary_file_inventory.tsv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["filename", "url", "size_bytes", "file_type", "download_decision", "decision_reason"], delimiter="\t")
            writer.writeheader()
            writer.writerows(inventory)
        status = write_gse338829(out_dir, summary, inventory, samples)
        gate = evaluate_quality_gate([str(out_dir / "GSE338829_sample_design.tsv")], [str(out_dir / "GSE338829_sample_design.tsv")])
        if not gate["quality_gate_passed"]:
            status = "INSUFFICIENT_DATA"
        write_status(out_dir / "status.json", f"{accession}_feasibility", status, run_id=args.run_id, errors=errors, **gate, outputs=[str(p) for p in out_dir.glob("*")])
        statuses[accession] = status
    write_status(out_root / "status.json", "dataset_feasibility", "COMPLETED_WITH_WARNINGS" if any(v in {"INSUFFICIENT_DATA", "METADATA_ONLY"} for v in statuses.values()) else "COMPLETED", run_id=args.run_id, dataset_status=statuses)
    print(out_root)


if __name__ == "__main__":
    main()
