import json
from pathlib import Path

from ovarian_ai.scoring.evidence_table import build_evidence_records


def test_candidate_source_dataset_mapping(tmp_path):
    gse319733 = tmp_path / "scrna"
    feasibility = tmp_path / "feasibility"
    (feasibility / "GSE338829").mkdir(parents=True)
    (feasibility / "GSE338829" / "GSE338829_assay_classification.json").write_text(json.dumps({"evidence_type": "RNA-binding target evidence"}), encoding="utf-8")
    records = build_evidence_records(gse319733, feasibility, "sha", "run")
    rbms1 = [row for row in records if row["gene"] == "RBMS1"][0]
    assert rbms1["source_dataset"] == "GSE338829"
