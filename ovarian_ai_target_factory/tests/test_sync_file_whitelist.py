from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from sync_results_to_github import exclusion_reason


def test_sync_file_whitelist_blocks_fastq(tmp_path):
    path = tmp_path / "reads.fastq.gz"
    path.write_text("x", encoding="utf-8")
    assert exclusion_reason(path, 10 * 1024 * 1024) == "suffix not allowed"


def test_sync_file_whitelist_allows_tsv(tmp_path):
    path = tmp_path / "summary.tsv"
    path.write_text("a\tb\n", encoding="utf-8")
    assert exclusion_reason(path, 10 * 1024 * 1024) == ""
