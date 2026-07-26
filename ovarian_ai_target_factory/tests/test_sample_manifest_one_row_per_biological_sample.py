from pathlib import Path
import importlib.util

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "05_validation" / "gse319733" / "02_build_sample_manifest.py"
spec = importlib.util.spec_from_file_location("build_sample_manifest", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_sample_manifest_one_row_per_biological_sample():
    rows = [
        {"filename": "GSM1_P1_LN_matrix.mtx.gz", "file_type": "gex_matrix", "patient_id": "P1", "tissue": "LN", "local_path": "m"},
        {"filename": "GSM1_P1_LN_barcodes.tsv.gz", "file_type": "gex_barcodes", "patient_id": "P1", "tissue": "LN", "local_path": "b"},
        {"filename": "GSM1_P1_LN_features.tsv.gz", "file_type": "gex_features", "patient_id": "P1", "tissue": "LN", "local_path": "f"},
        {"filename": "GSM2_P1_LN_all_contig_annotations.csv.gz", "file_type": "vdj_contigs", "patient_id": "P1", "tissue": "LN", "local_path": "v"},
    ]
    manifest, errors = mod.build_manifest(rows)
    assert len(manifest) == 1
    assert manifest[0]["biological_sample_id"] == "P1_LN"
    assert manifest[0]["has_gex"] == "true"
    assert manifest[0]["has_vdj"] == "true"
