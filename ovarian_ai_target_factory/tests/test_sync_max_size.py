from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from sync_results_to_github import exclusion_reason


def test_sync_max_size_blocks_large_file(tmp_path):
    path = tmp_path / "large.tsv"
    path.write_bytes(b"0" * 11)
    assert exclusion_reason(path, 10) == "file exceeds max-file-mb"
