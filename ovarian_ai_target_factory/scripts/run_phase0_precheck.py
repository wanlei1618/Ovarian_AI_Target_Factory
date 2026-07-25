from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.utils.paths import ensure_subdirs
from ovarian_ai.utils.run_status import make_run_id, write_status


def run_cmd(args: list[str], cwd: Path = REPO_ROOT) -> dict:
    try:
        result = subprocess.run(args, cwd=str(cwd), text=True, capture_output=True, timeout=30)
        return {"cmd": args, "returncode": result.returncode, "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
    except Exception as exc:
        return {"cmd": args, "returncode": 1, "stdout": "", "stderr": str(exc)}


def find_rscript() -> str:
    found = shutil.which("Rscript")
    if found:
        return found
    for candidate in (
        Path("D:/R/R-4.6.1/bin/Rscript.exe"),
        Path("D:/R/R-4.6.1/bin/x64/Rscript.exe"),
        Path("D:/R/R-4.0.3/bin/Rscript.exe"),
        Path("D:/R/R-4.0.3/bin/x64/Rscript.exe"),
    ):
        if candidate.exists():
            return str(candidate)
    return ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "paths.yaml")
    args = parser.parse_args()
    run_id = args.run_id or make_run_id(REPO_ROOT)
    dirs = ensure_subdirs(args.config)
    outdir = dirs["results"] / "pipeline_qc" / run_id
    outdir.mkdir(parents=True, exist_ok=True)
    rscript = find_rscript()
    checks = {
        "git_status": run_cmd(["git", "status", "--short"]),
        "git_remote": run_cmd(["git", "remote", "-v"]),
        "git_branch": run_cmd(["git", "branch", "--show-current"]),
        "python_version": run_cmd(["python", "--version"]),
        "rscript_path": rscript,
        "rscript_version": run_cmd([rscript, "--version"]) if rscript else {"returncode": 1, "stderr": "Rscript not found"},
        "git_version": run_cmd(["git", "--version"]),
        "gh_version": run_cmd(["D:/Tools/gh/gh.exe", "--version"]),
        "disk_usage": {
            "data_root": str(dirs["root"]),
            "data_root_free_gb": round(shutil.disk_usage(dirs["root"]).free / (1024**3), 2),
            "c_drive_free_gb": round(shutil.disk_usage("C:/").free / (1024**3), 2),
        },
    }
    status = "COMPLETED" if rscript else "COMPLETED_WITH_WARNINGS"
    (outdir / "environment_precheck.json").write_text(json.dumps(checks, indent=2, ensure_ascii=False), encoding="utf-8")
    write_status(outdir / "status.json", "phase0_precheck", status, run_id=run_id, outputs=[str(outdir / "environment_precheck.json")])
    print(run_id)


if __name__ == "__main__":
    main()
