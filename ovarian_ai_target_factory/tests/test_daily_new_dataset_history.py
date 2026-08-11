from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.datasets.dataset_watcher import update_dataset_history


def test_daily_new_dataset_history(tmp_path):
    history = tmp_path / "dataset_history.tsv"
    rows = update_dataset_history(history, [{"dataset_id": "GSE900001", "title": "first", "modality": "RNA-seq", "dataset_action": "needs_manual_review", "source_type": "auto_geo_search"}], "2026-07-25")
    assert rows[0]["first_seen_date"] == "2026-07-25"
    assert rows[0]["times_seen"] == "1"
