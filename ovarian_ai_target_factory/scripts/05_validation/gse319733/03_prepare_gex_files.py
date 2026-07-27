from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.utils.paths import ensure_subdirs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "paths.yaml")
    args = parser.parse_args()
    dirs = ensure_subdirs(args.config)
    out_dir = dirs["results"] / "scrna" / "GSE319733" / args.run_id
    status_path = out_dir / "status.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
    if status.get("analysis_status") != "COMPLETED":
        (out_dir / "NOT_RUN_reason.txt").write_text(
            "GEX preparation blocked because complete directly downloadable processed matrix/barcode/features files are unavailable. RAW.tar was not downloaded by policy.\n",
            encoding="utf-8",
        )
    print(out_dir)


if __name__ == "__main__":
    main()
