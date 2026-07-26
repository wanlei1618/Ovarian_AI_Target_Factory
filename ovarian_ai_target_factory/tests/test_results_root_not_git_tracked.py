import subprocess
from pathlib import Path


def test_results_root_not_git_tracked():
    repo = Path(__file__).resolve().parents[2]
    tracked = subprocess.check_output(["git", "ls-files", "results"], cwd=str(repo), text=True).splitlines()
    assert tracked == []
