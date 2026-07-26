from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


VALID_STATUSES = {
    "NOT_STARTED",
    "RUNNING",
    "METADATA_ONLY",
    "INSUFFICIENT_DATA",
    "COMPLETED",
    "COMPLETED_WITH_WARNINGS",
    "FAILED",
    "BLOCKED",
}


def short_git_sha(repo_root: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=str(repo_root), text=True).strip()
    except Exception:
        return "nogit"


def make_run_id(repo_root: Path) -> str:
    return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{short_git_sha(repo_root)}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tsv_data_row_count(path: Path) -> int:
    if not path.exists() or path.stat().st_size == 0:
        return 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        lines = [line for line in handle if line.strip()]
    return max(len(lines) - 1, 0)


def evaluate_quality_gate(required_outputs: list[str] | None = None, required_nonempty_outputs: list[str] | None = None) -> dict:
    required_outputs = required_outputs or []
    required_nonempty_outputs = required_nonempty_outputs or []
    missing = [path for path in required_outputs if not Path(path).exists()]
    row_counts = {path: tsv_data_row_count(Path(path)) for path in required_nonempty_outputs}
    empty = [path for path, count in row_counts.items() if count < 1]
    passed = not missing and not empty
    reason = ""
    if missing:
        reason = "missing required outputs: " + "; ".join(missing)
    elif empty:
        reason = "required tables have no data rows: " + "; ".join(empty)
    return {
        "quality_gate_passed": passed,
        "required_outputs": required_outputs,
        "required_nonempty_outputs": required_nonempty_outputs,
        "row_counts": row_counts,
        "blocking_reason": reason,
    }


def write_status(path: Path, module: str, status: str, **kwargs: Any) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "module": module,
        "analysis_status": status,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        **kwargs,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
