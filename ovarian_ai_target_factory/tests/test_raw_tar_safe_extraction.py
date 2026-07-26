from pathlib import Path
import importlib.util


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "05_validation" / "gse319733" / "00_download_extract_raw_tar.py"
spec = importlib.util.spec_from_file_location("download_extract_raw_tar", SCRIPT)
tar_script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tar_script)


def test_raw_tar_rejects_path_traversal_name():
    assert tar_script.allowed_member("../evil_matrix.mtx.gz") is False
    assert tar_script.allowed_member("/abs_matrix.mtx.gz") is False
