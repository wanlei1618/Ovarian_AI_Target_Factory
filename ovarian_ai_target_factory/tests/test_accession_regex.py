from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.literature.literature_watcher import extract_accessions


def test_accession_regex_extracts_public_data_accessions():
    hits = extract_accessions("Data are in GSE123456, SRP999999 and PRJNA123456.")
    assert {item["accession"] for item in hits} == {"GSE123456", "SRP999999", "PRJNA123456"}
