from __future__ import annotations

import argparse
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
    manifest = dirs["results"] / "scrna" / "GSE319733" / args.run_id / "sample_manifest.tsv"
    if not manifest.exists():
        raise SystemExit("sample_manifest.tsv not found; run 01_inventory_gse319733.py first")
    print(manifest)


if __name__ == "__main__":
    main()
