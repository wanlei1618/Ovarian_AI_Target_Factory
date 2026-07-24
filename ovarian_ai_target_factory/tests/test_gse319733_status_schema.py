import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.utils.run_status import write_status


def test_gse319733_status_schema(tmp_path):
    status = tmp_path / "status.json"
    write_status(status, "GSE319733_analysis", "BLOCKED", run_id="run", warnings=[], errors=[])
    payload = json.loads(status.read_text(encoding="utf-8"))
    assert payload["module"] == "GSE319733_analysis"
    assert payload["analysis_status"] == "BLOCKED"
    assert payload["run_id"] == "run"
