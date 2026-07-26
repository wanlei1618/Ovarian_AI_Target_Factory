from pathlib import Path

from ovarian_ai.utils.run_status import evaluate_quality_gate


def test_empty_manifest_not_completed(tmp_path):
    table = tmp_path / "donor_manifest.tsv"
    table.write_text("donor_id\tdisease_group\n", encoding="utf-8")
    gate = evaluate_quality_gate([str(table)], [str(table)])
    assert gate["quality_gate_passed"] is False
    assert gate["row_counts"][str(table)] == 0
