from pathlib import Path
import importlib.util

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "05_validation" / "gse319733" / "02_build_sample_manifest.py"
spec = importlib.util.spec_from_file_location("build_sample_manifest_pairing", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_gse319733_expected_pairing_qc():
    rows = []
    for patient in ["P1", "P2", "P3", "P4"]:
        for tissue in ["LN", "PT"]:
            rows.append({"filename": f"GSM_{patient}_{tissue}_matrix.mtx.gz", "file_type": "gex_matrix", "patient_id": patient, "tissue": tissue, "local_path": "m"})
            rows.append({"filename": f"GSM_{patient}_{tissue}_barcodes.tsv.gz", "file_type": "gex_barcodes", "patient_id": patient, "tissue": tissue, "local_path": "b"})
            rows.append({"filename": f"GSM_{patient}_{tissue}_features.tsv.gz", "file_type": "gex_features", "patient_id": patient, "tissue": tissue, "local_path": "f"})
    manifest, _ = mod.build_manifest(rows)
    paired = {row["patient_id"] for row in manifest if row["paired_patient"] == "true"}
    assert {"P1", "P2", "P3", "P4"}.issubset(paired)
