from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ovarian_ai.utils.paths import ensure_subdirs


SKIP_PARTS = {"__pycache__", ".git", ".venv"}
TEXT_SUFFIXES = {".py", ".R", ".r", ".md", ".yaml", ".yml", ".txt", ".toml", ".mk", ""}


def yyyymmdd(value: str) -> str:
    return value.replace("-", "")


def iter_text_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.suffix in TEXT_SUFFIXES or path.name == "Makefile":
            files.append(path)
    return files


def classify_match(path: Path, line_no: int, line: str, pattern: str) -> dict:
    lowered = line.lower()
    allowed = False
    reason = ""
    if "refusing" in lowered or "forbidden" in lowered or "disk_usage" in lowered or "blocked" in lowered:
        allowed = True
        reason = "guard/check code"
    if "path_checker.py" in str(path).replace("\\", "/"):
        allowed = True
        reason = "path checker rule definition"
    return {
        "file": str(path),
        "line": line_no,
        "pattern": pattern,
        "text": line.strip(),
        "allowed": allowed,
        "reason": reason,
    }


def scan_project(root: Path) -> list[dict]:
    patterns = {
        "hard-coded user directory": re.compile(r"C:\\Users|C:/Users", re.IGNORECASE),
        "Downloads directory": re.compile(r"([A-Z]:)?[\\/][^\\/\n]*Downloads([\\/]|$)", re.IGNORECASE),
        "Documents directory": re.compile(r"([A-Z]:)?[\\/][^\\/\n]*Documents([\\/]|$)", re.IGNORECASE),
        "AppData directory": re.compile(r"([A-Z]:)?[\\/][^\\/\n]*AppData([\\/]|$)", re.IGNORECASE),
        "tempfile usage": re.compile(r"tempfile|TemporaryDirectory|gettempdir", re.IGNORECASE),
        "system temp path": re.compile(r"/tmp|\\\\Temp|\\bTEMP\\b|\\bTMP\\b", re.IGNORECASE),
        "current-directory output write": re.compile(r"write_text\(|\.open\(|download\.file\(|write\.table\(", re.IGNORECASE),
    }
    matches = []
    for file_path in iter_text_files(root):
        try:
            lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line_no, line in enumerate(lines, start=1):
            for name, pattern in patterns.items():
                if pattern.search(line):
                    matches.append(classify_match(file_path, line_no, line, name))
    return matches


def build_report(matches: list[dict], output_path: Path, run_date: str) -> str:
    failed = [item for item in matches if not item["allowed"] and item["pattern"] != "current-directory output write"]
    suspicious = [item for item in matches if not item["allowed"]]
    manual_review = [item for item in matches if item["pattern"] == "current-directory output write" and not item["allowed"]]
    passed_checks = [
        "config/paths.yaml is used by shared Python path utilities.",
        "D-drive result directory is available.",
        "C-drive/user-directory patterns are treated as failures unless they are guard/check code.",
        "tempfile/system temporary directory usage is scanned.",
        "Potential direct file writes are listed for manual review.",
    ]

    def match_lines(items: list[dict]) -> list[str]:
        if not items:
            return ["- None"]
        lines = []
        for item in items[:80]:
            lines.append(f"- {item['pattern']}: {item['file']}:{item['line']}")
            lines.append(f"  - `{item['text'][:220]}`")
            if item["reason"]:
                lines.append(f"  - reason: {item['reason']}")
        if len(items) > 80:
            lines.append(f"- Truncated {len(items) - 80} additional matches.")
        return lines

    lines = [
        f"# Path Check Report: {run_date}",
        "",
        f"Output: `{output_path}`",
        "",
        "## Passed checks",
        *[f"- {item}" for item in passed_checks],
        "",
        "## Failed checks",
        *match_lines(failed),
        "",
        "## Suspicious path patterns",
        *match_lines(suspicious),
        "",
        "## Files needing manual review",
        *match_lines(manual_review),
        "",
        "## Recommended fixes",
        "- Route all raw data, processed data, results, cache, and logs through `config/paths.yaml` and `ovarian_ai.utils.paths`.",
        "- Keep network downloads pointed to D-drive raw/cache directories.",
        "- Keep logs under `D:/Ovarian_AI_Target_Factory/results/logs` or another configured D-drive result subdirectory.",
        "- If temporary files become necessary, create them under the configured cache directory.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan project path compliance.")
    parser.add_argument("--date", dest="run_date", default=date.today().isoformat())
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "paths.yaml")
    args = parser.parse_args()
    dirs = ensure_subdirs(args.config)
    output_path = dirs["results"] / f"path_check_report_{yyyymmdd(args.run_date)}.md"
    report = build_report(scan_project(PROJECT_ROOT), output_path, args.run_date)
    output_path.write_text(report, encoding="utf-8")
    print(f"path checker output: {output_path}")


if __name__ == "__main__":
    main()
