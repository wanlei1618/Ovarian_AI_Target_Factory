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
