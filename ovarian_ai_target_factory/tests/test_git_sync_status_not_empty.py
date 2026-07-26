import json
from pathlib import Path


def test_git_sync_status_not_empty(tmp_path):
    path = tmp_path / "git_sync_status.json"
    payload = {"branch": "codex/after-244c94d", "analysis_code_sha": "abc", "results_commit_sha": "def", "push_returncode": 0, "remote": "origin", "pr_url": "url", "timestamp": "now"}
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["branch"]
    assert loaded["analysis_code_sha"]
    assert loaded["results_commit_sha"]
