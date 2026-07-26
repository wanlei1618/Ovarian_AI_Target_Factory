from pathlib import Path
import importlib.util

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "05_validation" / "gse319733" / "00_download_extract_raw_tar.py"
spec = importlib.util.spec_from_file_location("download_extract_raw_tar", SCRIPT)
tar_script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tar_script)


def test_raw_tar_member_whitelist():
    assert tar_script.allowed_member("GSM1_P1_LN_matrix.mtx.gz") is True
    assert tar_script.allowed_member("GSM1_P1_LN_barcodes.tsv.gz") is True
    assert tar_script.allowed_member("GSM1_P1_LN_features.tsv.gz") is True
    assert tar_script.allowed_member("GSM1_P1_LN_all_contig_annotations.csv.gz") is True
    assert tar_script.allowed_member("reads.fastq.gz") is False
    assert tar_script.allowed_member("alignment.bam") is False
