from __future__ import annotations

import runpy
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "gse319733_analysis.py"
runpy.run_path(str(SCRIPT), run_name="__main__")
