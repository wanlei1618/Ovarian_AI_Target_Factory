from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.literature.literature_watcher import refine_literature_record


def test_public_data_requires_verified_accession():
    refined = refine_literature_record({"title": "Ovarian cancer study", "abstract": "We mention GEO generally but provide no accession.", "article_type": []})
    assert refined["public_data_claimed"] is False
    assert refined["public_data_verified"] is False
