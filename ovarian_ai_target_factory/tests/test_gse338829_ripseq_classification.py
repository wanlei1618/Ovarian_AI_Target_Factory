from pathlib import Path
import importlib.util

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "02_dataset_feasibility" / "geo_feasibility_check.py"
spec = importlib.util.spec_from_file_location("geo_feasibility_check", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_gse338829_ripseq_classification(tmp_path):
    status = mod.write_gse338829(
        tmp_path,
        {"title": "RBMS1 RIP-seq identifies NEDD4 RNA targets", "summary": "RNA immunoprecipitation"},
        [],
        [{"sample_id": "GSM1", "title": "RBMS1 IP replicate 1", "source_name": "OVCAR8", "characteristics": "RIP-seq"}],
    )
    assert status == "METADATA_ONLY"
    text = (tmp_path / "GSE338829_assay_classification.json").read_text(encoding="utf-8")
    assert '"assay_type": "RIP-seq"' in text
    assert '"evidence_type": "RNA-binding target evidence"' in text
