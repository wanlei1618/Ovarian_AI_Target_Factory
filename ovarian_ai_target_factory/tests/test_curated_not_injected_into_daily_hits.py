from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.datasets.dataset_watcher import newly_detected_records


def test_curated_not_injected_into_daily_hits():
    rows = [{"dataset_id": "GSE319733"}, {"dataset_id": "GSE900001"}]
    assert newly_detected_records(rows, {"GSE319733"}) == [{"dataset_id": "GSE900001"}]
