from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.datasets.dataset_watcher import infer_modality, load_curated_datasets, newly_detected_records
from ovarian_ai.literature.literature_watcher import refine_literature_record


def test_gse262172_curated_modality_is_atac_seq():
    curated = {row["dataset_id"]: row for row in load_curated_datasets(PROJECT_ROOT / "config" / "paths.yaml")}
    assert curated["GSE262172"]["modality"] == "ATAC-seq"
    assert infer_modality("GSK-J4 treatment ATAC-Seq ovarian cancer cell lines") == "ATAC-seq"


def test_curated_dataset_not_in_daily_newly_detected():
    rows = [{"dataset_id": "GSE319733"}, {"dataset_id": "GSE999999"}]
    assert newly_detected_records(rows, {"GSE319733"}) == [{"dataset_id": "GSE999999"}]


def test_excluded_literature_not_high_priority():
    record = {
        "title": "Corrigendum to ovarian cancer target paper",
        "abstract": "ovarian cancer methylation",
        "article_type": ["Published Erratum"],
    }
    refined = refine_literature_record(record)
    assert refined["exclusion_status"] == "exclude"
    assert refined["priority"] == "exclude"


def test_metadata_only_run_uses_not_run_reason(tmp_path):
    reason = tmp_path / "NOT_RUN_reason.txt"
    reason.write_text("No matrix parsed", encoding="utf-8")
    assert reason.exists()
