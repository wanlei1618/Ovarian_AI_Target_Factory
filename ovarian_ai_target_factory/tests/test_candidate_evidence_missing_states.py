from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.scoring.evidence_table import EVIDENCE_STATES, build_candidate_rows


def test_candidate_evidence_missing_states_are_not_zero(tmp_path):
    rows = build_candidate_rows(tmp_path)
    assert rows
    for row in rows:
        assert row["tumor_expression"] in EVIDENCE_STATES
        assert row["total_score"] == ""
        assert row["decision"] == "INSUFFICIENT_DATA"
