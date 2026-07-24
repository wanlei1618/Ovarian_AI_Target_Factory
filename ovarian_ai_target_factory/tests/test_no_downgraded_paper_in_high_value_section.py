import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.report.report_generator import build_daily_report


def test_no_downgraded_paper_in_high_value_section(tmp_path):
    suffix = "20260724"
    records = [{"title": "COX-1 mofezolac prognostic model", "priority": "low", "exclusion_status": "downgrade"}]
    (tmp_path / f"refined_literature_digest_{suffix}.json").write_text(json.dumps(records), encoding="utf-8")
    (tmp_path / f"daily_newly_detected_datasets_{suffix}.tsv").write_text("dataset_id\ttitle\n", encoding="utf-8")
    (tmp_path / "curated_dataset_registry.tsv").write_text("dataset_id\ttitle\tdataset_action\n", encoding="utf-8")
    report = build_daily_report("2026-07-24", tmp_path)
    high_section = report.split("## 2. Background/method papers")[0]
    assert "COX-1 mofezolac" not in high_section
