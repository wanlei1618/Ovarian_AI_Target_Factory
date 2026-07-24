from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def test_no_placeholder_expression_pdf_in_script():
    script = PROJECT_ROOT / "scripts" / "05_validation" / "gse319733_analysis.py"
    text = script.read_text(encoding="utf-8").lower()
    assert "umap_celltype.pdf" not in text
    assert "dotplot" not in text
