from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.literature.literature_watcher import extract_accessions


def test_pdb_id_not_geo_accession():
    assert extract_accessions("Protein model 1GSE and DOI 10.1000/gse.test were cited.") == []
