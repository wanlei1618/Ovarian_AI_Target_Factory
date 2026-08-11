from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import tarfile
import time
import urllib.request
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.utils.paths import ensure_subdirs
from ovarian_ai.utils.run_status import sha256_file, write_status


URL = "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE319nnn/GSE319733/suppl/GSE319733_RAW.tar"
EXPECTED_MIN_BYTES = 300_000_000
EXPECTED_MAX_BYTES = 1_073_741_824
ALLOW_PATTERNS = [
    re.compile(r"(^|.*/)[^/]*_matrix\.mtx\.gz$"),
    re.compile(r"(^|.*/)[^/]*_barcodes\.tsv\.gz$"),
    re.compile(r"(^|.*/)[^/]*_features\.tsv\.gz$"),
    re.compile(r"(^|.*/)[^/]*_GEO_Metadata_[^/]*\.csv\.gz$"),
    re.compile(r"(^|.*/)[^/]*_all_contig_annotations\.csv\.gz$"),
]


def classify(name: str) -> str:
    lower = name.lower()
    if "matrix.mtx" in lower:
        return "gex_matrix"
    if "barcodes.tsv" in lower:
        return "gex_barcodes"
    if "features.tsv" in lower:
        return "gex_features"
    if "geo_metadata" in lower:
        return "cell_metadata"
    if "all_contig_annotations" in lower:
        return "vdj_contigs"
    return "unknown"


def parse_name(name: str) -> dict:
    base = Path(name).name
    patient = re.search(r"_(P\d+)_", base)
    tissue = re.search(r"_(LN|PT)_", base)
    gsm = re.match(r"(GSM\d+)_", base)
    return {
        "gsm": gsm.group(1) if gsm else "",
        "patient_id": patient.group(1) if patient else "",
        "tissue": tissue.group(1) if tissue else "",
    }


def allowed_member(name: str) -> bool:
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or ".." in normalized.split("/"):
        return False
    if normalized.lower().endswith((".fastq", ".fastq.gz", ".fq", ".fq.gz", ".bam")):
        return False
    return any(pattern.search(normalized) for pattern in ALLOW_PATTERNS)


def download_archive(path: Path, max_archive_gb: float) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + ".part")
    max_bytes = int(max_archive_gb * 1024**3)
    if path.exists() and EXPECTED_MIN_BYTES <= path.stat().st_size <= max_bytes:
        return {"downloaded": False, "size_bytes": path.stat().st_size, "sha256": sha256_file(path), "url": URL, "path": str(path)}
    for attempt in range(1, 4):
        try:
            request = urllib.request.Request(URL, headers={"User-Agent": "OvarianAITargetFactory/raw-tar-approved"})
            with urllib.request.urlopen(request, timeout=120) as response, part.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
            size = part.stat().st_size
            if size < EXPECTED_MIN_BYTES or size > max_bytes:
                raise RuntimeError(f"archive size {size} outside allowed range")
            part.replace(path)
            return {"downloaded": True, "size_bytes": path.stat().st_size, "sha256": sha256_file(path), "url": URL, "path": str(path)}
        except Exception as exc:
            if attempt == 3:
                raise
            time.sleep(5 * attempt)
    raise RuntimeError("download failed")


def safe_extract(archive: Path, out_dir: Path) -> tuple[list[dict], list[dict]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    member_rows = []
    extracted = []
    with tarfile.open(archive, "r") as tar:
        for member in tar.getmembers():
            name = member.name.replace("\\", "/")
            allowed = member.isfile() and allowed_member(name)
            file_type = classify(name)
            member_rows.append(
                {
                    "archive_member": name,
                    "size_bytes": member.size,
                    "file_type": file_type,
                    "allowed_by_whitelist": str(allowed).lower(),
                    "source_container": archive.name,
                }
            )
            if not allowed:
                continue
            target = out_dir / Path(name).name
            resolved = target.resolve()
            if out_dir.resolve() not in resolved.parents:
                raise RuntimeError(f"unsafe extraction target: {target}")
            with tar.extractfile(member) as source, target.open("wb") as dest:
                if source is None:
                    continue
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    dest.write(chunk)
            parsed = parse_name(name)
            extracted.append(
                {
                    "filename": target.name,
                    "archive_member": name,
                    "size_bytes": target.stat().st_size,
                    "file_type": file_type,
                    "patient_id": parsed["patient_id"],
                    "tissue": parsed["tissue"],
                    "library_type": "GEX" if file_type.startswith("gex") or file_type == "cell_metadata" else "VDJ",
                    "local_path": str(target),
                    "sha256": sha256_file(target),
                    "extraction_status": "EXTRACTED",
                }
            )
    return member_rows, extracted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "paths.yaml")
    parser.add_argument("--max-archive-gb", type=float, default=1.0)
    parser.add_argument("--keep-archive", action="store_true")
    args = parser.parse_args()
    dirs = ensure_subdirs(args.config)
    raw_root = dirs["raw"] / "single_cell" / "GSE319733"
    archive = raw_root / "archives" / "GSE319733_RAW.tar"
    extracted_dir = raw_root / "processed_from_RAW"
    out_dir = dirs["results"] / "scrna" / "GSE319733" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    errors = []
    try:
        download_info = download_archive(archive, args.max_archive_gb)
        member_rows, extracted = safe_extract(archive, extracted_dir)
    except Exception as exc:
        download_info = {"url": URL, "path": str(archive), "error": str(exc)}
        member_rows, extracted = [], []
        errors.append(str(exc))

    (out_dir / "archive_download_manifest.json").write_text(json.dumps({**download_info, "timestamp": datetime.now().isoformat(timespec="seconds")}, indent=2, ensure_ascii=False), encoding="utf-8")
    with (out_dir / "archive_member_inventory.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["archive_member", "size_bytes", "file_type", "allowed_by_whitelist", "source_container"], delimiter="\t")
        writer.writeheader()
        writer.writerows(member_rows)
    with (out_dir / "extracted_file_manifest.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["filename", "archive_member", "size_bytes", "file_type", "patient_id", "tissue", "library_type", "local_path", "sha256", "extraction_status"], delimiter="\t")
        writer.writeheader()
        writer.writerows(extracted)
    status = "COMPLETED" if extracted and not errors else "FAILED"
    write_status(
        out_dir / "download_extract_status.json",
        "GSE319733_download_extract",
        status,
        run_id=args.run_id,
        quality_gate_passed=bool(extracted and not errors),
        required_outputs=[str(out_dir / "archive_download_manifest.json"), str(out_dir / "archive_member_inventory.tsv"), str(out_dir / "extracted_file_manifest.tsv")],
        required_nonempty_outputs=[str(out_dir / "extracted_file_manifest.tsv")],
        row_counts={str(out_dir / "extracted_file_manifest.tsv"): len(extracted)},
        blocking_reason="; ".join(errors),
        archive_only_layout_detected=True,
        direct_member_download_attempts=0,
    )
    print(out_dir)


if __name__ == "__main__":
    main()
