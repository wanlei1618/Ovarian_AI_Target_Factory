from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def test_gse337706_expected_classification_text():
    script = PROJECT_ROOT / "scripts" / "02_dataset_feasibility" / "geo_feasibility_check.py"
    text = script.read_text(encoding="utf-8")
    assert "ovarian liquid biopsy / platelet-coated CTC" in text
    assert "main_project_relevance: medium-low" in text
