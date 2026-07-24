from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.report.report_generator import build_daily_report


def test_empty_high_value_section_is_explicit(tmp_path):
    suffix = "20260724"
    (tmp_path / f"refined_literature_digest_{suffix}.json").write_text("[]", encoding="utf-8")
    (tmp_path / f"daily_newly_detected_datasets_{suffix}.tsv").write_text("dataset_id\ttitle\n", encoding="utf-8")
    (tmp_path / "curated_dataset_registry.tsv").write_text("dataset_id\ttitle\tdataset_action\n", encoding="utf-8")
    report = build_daily_report("2026-07-24", tmp_path)
    assert "- None retained after refined evidence filtering." in report
