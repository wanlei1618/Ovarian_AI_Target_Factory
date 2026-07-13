from __future__ import annotations

import argparse
import csv
import json
import logging
from datetime import date
from pathlib import Path

from ovarian_ai.utils.paths import assert_not_c_data_path, daily_reports_root


def yyyymmdd(value: str) -> str:
    return value.replace("-", "")


def setup_logger(outdir: Path, run_date: str) -> logging.Logger:
    logger = logging.getLogger("report_generator")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.FileHandler(outdir / "logs" / f"report_generator_{yyyymmdd(run_date)}.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def _read_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def _read_tsv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def build_daily_report(run_date: str, report_dir: Path) -> str:
    suffix = yyyymmdd(run_date)
    literature = _read_json(report_dir / f"literature_digest_{suffix}.json")
    datasets = _read_tsv(report_dir / f"new_dataset_registry_{suffix}.tsv")

    lines = [
        f"# Daily Ovarian AI Target Report: {run_date}",
        "",
        "## 1. New high-value papers",
    ]
    if literature:
        for item in literature:
            lines.extend(
                [
                    f"- {item['title']}",
                    f"  - journal/preprint server: {item['journal']}",
                    f"  - publication date: {item['date']}",
                    f"  - modality: {', '.join(item.get('modality') or [])}",
                    f"  - available data/code: {item['data_availability']} / {item['code_availability']}",
                    f"  - relevance: {item['reason']}",
                    f"  - priority: {item['priority']}",
                ]
            )
    else:
        lines.append("- No literature records found for this MVP run.")

    lines.extend(["", "## 2. New datasets"])
    if datasets:
        for item in datasets:
            lines.extend(
                [
                    f"- {item['dataset_id']}: {item['title']}",
                    f"  - sample count: {item['sample_count']}",
                    f"  - modality: {item['modality']}",
                    f"  - download URL: {item['download_url']}",
                    f"  - priority score: {item['priority_score']}",
                    f"  - recommended action: {item['recommended_action']}",
                ]
            )
    else:
        lines.append("- No dataset records found for this MVP run.")

    lines.extend(
        [
            "",
            "## 3. New strategies worth learning",
            "- PubMed metadata triage: prioritize papers with ovarian cancer plus single-cell, spatial, multi-omics, dependency, or resistance terms.",
            "- GEO metadata triage: review high-score GSE records first, then approve only small metadata-safe downloads in the next phase.",
            "",
            "## 4. Candidate target changes",
            "- New candidates: none yet; MVP v0.1 is metadata-only.",
            "- Evidence strengthened: none yet.",
            "- Evidence weakened: none yet.",
            "- Suggested removals: none yet.",
            "",
            "## 5. Questions for ChatGPT judgment",
            "- Which PubMed/GEO hits should be promoted to manual review?",
            "- Which evidence type is most publishable for a short-term ovarian cancer project?",
            "- Which GEO datasets should be approved for metadata-only or small-sample download next?",
            "",
            "## 6. Next Codex tasks",
            "- script: refine PubMed and GEO ranking heuristics.",
            "- input: reviewed search terms and manual inclusion/exclusion feedback.",
            "- output: cleaner literature digest and dataset registry.",
            "- success criteria: no large downloads; all outputs remain under D:/Ovarian_AI_Target_Factory/results.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_next_action_report(run_date: str, report_dir: Path) -> str:
    suffix = yyyymmdd(run_date)
    literature = _read_json(report_dir / f"refined_literature_digest_{suffix}.json")
    datasets = _read_tsv(report_dir / f"refined_dataset_registry_{suffix}.tsv")

    def dataset_lines(title: str, actions: set[str]) -> list[str]:
        selected = [item for item in datasets if item.get("dataset_action") in actions]
        lines = [f"## {title}"]
        if not selected:
            return lines + ["- None", ""]
        for item in selected:
            lines.extend(
                [
                    f"- {item.get('dataset_id')}: {item.get('title')}",
                    f"  - action: {item.get('dataset_action')}",
                    f"  - reason: {item.get('action_reason')}",
                    f"  - branch: {item.get('branch_project')}",
                ]
            )
        return lines + [""]

    def literature_lines(title: str, predicate) -> list[str]:
        selected = [item for item in literature if predicate(item)]
        lines = [f"## {title}"]
        if not selected:
            return lines + ["- None", ""]
        for item in selected:
            lines.extend(
                [
                    f"- {item.get('title')}",
                    f"  - PMID: {item.get('pmid', '')}",
                    f"  - priority: {item.get('priority', '')}",
                    f"  - exclusion_status: {item.get('exclusion_status', '')}",
                    f"  - reason: {item.get('exclusion_reason') or item.get('downgrade_reason') or item.get('false_positive_reason')}",
                ]
            )
        return lines + [""]

    lines = [f"# Next Action Report: {run_date}", ""]
    lines += dataset_lines("1. Approved downloads today", {"approve_download"})
    lines += dataset_lines("2. Deferred downloads today", {"defer", "needs_manual_review"})
    lines += dataset_lines("3. Metadata-only datasets today", {"metadata_only"})
    lines += literature_lines("4. Excluded or downgraded literature today", lambda item: item.get("exclusion_status") in {"exclude", "downgrade"})
    lines += literature_lines("5. False positive literature today", lambda item: bool(item.get("false_positive_reason")))
    lines += literature_lines("6. Literature still worth manual review", lambda item: item.get("priority") in {"high", "medium-high", "needs_manual_review"})
    lines.extend(
        [
            "## 7. New branch directions today",
            "- B-cell / tumor-draining lymph node immune niche in ovarian cancer: use GSE319733 for metadata-first lightweight exploration.",
            "- Chromatin accessibility and epigenetic drug response: keep GSE262172 as metadata-only until ATAC workflow is approved.",
            "- Mucinous ovarian carcinoma methylation classification: keep GSE310580 as a diagnostic ML branch, not the current HGSOC mainline.",
            "",
            "## 8. Next Codex tasks",
            "- Run the GSE319733 lightweight metadata parser and inspect supplementary file sizes.",
            "- If file sizes are acceptable, parse only approved GEX/BCR matrices from D-drive raw data.",
            "- Improve PubMed filtering with manual labels from the audit report.",
            "- Add duplicate handling and accession extraction for literature records.",
            "",
            "## 9. Questions for ChatGPT judgment",
            "- Should GSE319733 become an immune-niche side branch or feed the main target discovery score?",
            "- Which retained papers deserve manual reading first?",
            "- Are SPP1/CD44/ITGB1 worth prioritizing as an immune-niche invasion axis after GSE319733 parsing?",
            "",
            "## 10. Path compliance summary",
            "- Raw data root: D:/Ovarian_AI_Target_Factory/data_raw",
            "- Processed data root: D:/Ovarian_AI_Target_Factory/data_processed",
            "- Results root: D:/Ovarian_AI_Target_Factory/results",
            "- Cache root: D:/Ovarian_AI_Target_Factory/cache",
            "- This report is generated under D:/Ovarian_AI_Target_Factory/results/daily_reports.",
            "- No C-drive output path is approved.",
            "",
        ]
    )
    return "\n".join(lines)


def run(mode: str = "daily", run_date: str | None = None, config: Path | None = None, outdir: Path | None = None, dry_run: bool = False) -> Path:
    if mode != "daily":
        raise ValueError("MVP report_generator currently supports --mode daily only.")
    selected_date = run_date or date.today().isoformat()
    report_dir = outdir or daily_reports_root(config)
    assert_not_c_data_path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "logs").mkdir(parents=True, exist_ok=True)
    logger = setup_logger(report_dir, selected_date)

    if dry_run:
        return report_dir

    suffix = yyyymmdd(selected_date)
    try:
        report = build_daily_report(selected_date, report_dir)
    except Exception as exc:
        logger.exception("Report generation failed: %s", exc)
        report = f"# Daily Ovarian AI Target Report: {selected_date}\n\nReport generation failed. See logs.\n"
    (report_dir / f"Daily_Ovarian_AI_Target_Report_{suffix}.md").write_text(report, encoding="utf-8")
    try:
        next_action_report = build_next_action_report(selected_date, report_dir)
    except Exception as exc:
        logger.exception("Next action report generation failed: %s", exc)
        next_action_report = f"# Next Action Report: {selected_date}\n\nNext action report generation failed. See logs.\n"
    (report_dir / f"Next_Action_Report_{suffix}.md").write_text(next_action_report, encoding="utf-8")
    (report_dir / "codex_next_tasks.md").write_text(
        "\n".join(
            [
                "# Next Codex Tasks",
                "",
                "- Review PubMed/GEO query quality.",
                "- Add deduplication and manual curation flags.",
                "- Add minimal candidate target table mock for weekly report testing.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    logger.info("Wrote daily report for %s", selected_date)
    return report_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate MVP daily evidence report.")
    parser.add_argument("--mode", default="daily")
    parser.add_argument("--date", dest="run_date")
    parser.add_argument("--config", type=Path, default=Path("config/paths.yaml"))
    parser.add_argument("--outdir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    outdir = run(args.mode, args.run_date, args.config, args.outdir, args.dry_run)
    print(f"report_generator output: {outdir}")


if __name__ == "__main__":
    main()
