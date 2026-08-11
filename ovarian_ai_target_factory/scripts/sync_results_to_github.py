from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT_DEFAULT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.utils.run_status import sha256_file


ALLOWED_SUFFIXES = {".md", ".txt", ".tsv", ".csv", ".json", ".yaml", ".yml", ".png", ".svg", ".pdf", ".html"}
BLOCKED_SUFFIXES = {".fastq", ".fq", ".bam", ".h5ad", ".h5", ".loom", ".rds", ".RDS", ".tar", ".gz", ".zip", ".7z"}
SECRET_PATTERNS = [re.compile(r"github_pat_[A-Za-z0-9_]+"), re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_\-]{16,}")]
BLOCKED_FILENAMES = {
    "celltype_annotation.tsv",
}


def is_secret(path: Path) -> bool:
    if path.suffix.lower() not in {".md", ".txt", ".tsv", ".csv", ".json", ".yaml", ".yml", ".py", ".R"}:
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def is_relevant_daily_report_file(path: Path, source: Path, date_token: str) -> bool:
    rel = path.relative_to(source)
    if len(rel.parts) != 1:
        return False
    keep_exact = {
        "curated_dataset_registry.tsv",
        "codex_next_tasks.md",
    }
    return path.name in keep_exact or date_token in path.name


def exclusion_reason(path: Path, max_bytes: int) -> str:
    if path.name in BLOCKED_FILENAMES:
        return "cell-level table excluded from GitHub sync"
    if path.suffix.lower() not in ALLOWED_SUFFIXES or path.name.endswith((".fastq.gz", ".fq.gz")) or path.suffix.lower() in {suffix.lower() for suffix in BLOCKED_SUFFIXES}:
        return "suffix not allowed"
    if path.stat().st_size > max_bytes:
        return "file exceeds max-file-mb"
    if is_secret(path):
        return "secret/token pattern detected"
    return ""


def copy_group(source: Path, dest: Path, max_bytes: int, date_token: str | None = None) -> tuple[list[dict], list[dict]]:
    synced, excluded = [], []
    if not source.exists():
        return synced, excluded
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        if date_token and not is_relevant_daily_report_file(path, source, date_token):
            excluded.append({"source": str(path), "size_bytes": path.stat().st_size, "reason": "not part of requested run/date"})
            continue
        rel = path.relative_to(source)
        reason = exclusion_reason(path, max_bytes)
        if reason:
            excluded.append({"source": str(path), "size_bytes": path.stat().st_size, "reason": reason})
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        src_sha = sha256_file(path)
        if target.exists() and sha256_file(target) == src_sha:
            action = "unchanged"
        else:
            shutil.copy2(path, target)
            action = "copied"
        synced.append({"source": str(path), "target": str(target), "size_bytes": path.stat().st_size, "sha256": src_sha, "action": action})
    return synced, excluded


def run_git(repo_root: Path, args: list[str]) -> dict:
    result = subprocess.run(["git"] + args, cwd=str(repo_root), text=True, capture_output=True)
    return {"cmd": "git " + " ".join(args), "returncode": result.returncode, "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-results-root", type=Path, default=REPO_ROOT_DEFAULT / "results")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT_DEFAULT)
    parser.add_argument("--branch", default="codex/next-analysis")
    parser.add_argument("--max-file-mb", type=float, default=10)
    parser.add_argument("--analysis-code-sha", default="")
    parser.add_argument("--results-commit-sha", default="")
    parser.add_argument("--pr-url", default="")
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args()
    max_bytes = int(args.max_file_mb * 1024 * 1024)
    date_token = args.run_id[:8]
    sync_root = args.repo_root / "ovarian_ai_target_factory" / "results_synced"
    groups = [
        (args.source_results_root / "pipeline_qc" / args.run_id, sync_root / "pipeline_qc" / args.run_id),
        (args.source_results_root / "daily_reports", sync_root / "daily_reports" / args.run_id, date_token),
        (args.source_results_root / "scrna" / "GSE319733" / args.run_id, sync_root / "scrna" / "GSE319733" / args.run_id),
        (args.source_results_root / "dataset_feasibility" / args.run_id, sync_root / "dataset_feasibility" / args.run_id),
        (args.source_results_root / "target_factory" / args.run_id, sync_root / "target_factory" / args.run_id),
        (args.source_results_root / "final_reports" / args.run_id, sync_root / "final_reports" / args.run_id),
    ]
    synced, excluded = [], []
    for group in groups:
        source, dest = group[0], group[1]
        group_date_token = group[2] if len(group) > 2 else None
        s, e = copy_group(source, dest, max_bytes, group_date_token)
        synced.extend(s)
        excluded.extend(e)
    manifest_dir = sync_root / "manifests" / args.run_id
    manifest_dir.mkdir(parents=True, exist_ok=True)
    for filename, rows, fields in (
        ("sync_manifest.tsv", synced, ["source", "target", "size_bytes", "sha256", "action"]),
        ("excluded_from_sync.tsv", excluded, ["source", "size_bytes", "reason"]),
    ):
        with (manifest_dir / filename).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    (manifest_dir / "sync_manifest.json").write_text(json.dumps({"synced": synced, "excluded": excluded}, indent=2, ensure_ascii=False), encoding="utf-8")
    git_results = []
    push_returncode = None
    if args.commit:
        git_results.append(run_git(args.repo_root, ["add", "ovarian_ai_target_factory/results_synced"]))
        git_results.append(run_git(args.repo_root, ["commit", "-m", f"chore: sync analysis outputs {args.run_id}"]))
    if args.push:
        push_result = run_git(args.repo_root, ["push", "-u", "origin", args.branch])
        push_returncode = push_result["returncode"]
        git_results.append(push_result)
    status_payload = {
        "branch": args.branch,
        "analysis_code_sha": args.analysis_code_sha,
        "results_commit_sha": args.results_commit_sha,
        "push_returncode": push_returncode,
        "remote": "origin",
        "pr_url": args.pr_url,
        "timestamp": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "git_commands": git_results,
    }
    (manifest_dir / "git_sync_status.json").write_text(json.dumps(status_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(manifest_dir)


if __name__ == "__main__":
    main()
