from ovarian_ai.scoring.evidence_table import build_candidate_rows_from_records


def test_evidence_records_required_before_scoring():
    rows = build_candidate_rows_from_records([])
    assert rows
    assert all(row["decision"] == "INSUFFICIENT_DATA" for row in rows)
    assert all(row["total_score"] == "" for row in rows)
