# Path Check Report: 2026-07-12

Output: `D:\Ovarian_AI_Target_Factory\results\path_check_report_20260712.md`

## Passed checks
- config/paths.yaml is used by shared Python path utilities.
- D-drive result directory is available.
- C-drive/user-directory patterns are treated as failures unless they are guard/check code.
- tempfile/system temporary directory usage is scanned.
- Potential direct file writes are listed for manual review.

## Failed checks
- None

## Suspicious path patterns
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\scripts\check_disk_usage.py:46
  - `log_path.write_text(text, encoding="utf-8")`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\scripts\05_validation\scrna_bcr_gse319733_pipeline.R:41
  - `utils::download.file(url, destfile = destfile, mode = "wb", quiet = TRUE)`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\scripts\05_validation\scrna_bcr_gse319733_pipeline.R:125
  - `utils::write.table(sample_qc, file.path(out_dir, "sample_qc_summary.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\scripts\05_validation\scrna_bcr_gse319733_pipeline.R:138
  - `utils::write.table(key_gene_table, file.path(out_dir, "key_gene_expression_by_tissue.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\scripts\05_validation\scrna_bcr_gse319733_pipeline.R:145
  - `utils::write.table(bcr_summary, file.path(out_dir, "bcr_basic_summary.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\src\ovarian_ai\datasets\dataset_watcher.py:312
  - `path.write_text("\n".join(lines), encoding="utf-8")`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\src\ovarian_ai\datasets\dataset_watcher.py:342
  - `with out_path.open("w", newline="", encoding="utf-8") as handle:`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\src\ovarian_ai\datasets\dataset_watcher.py:346
  - `with refined_path.open("w", newline="", encoding="utf-8") as handle:`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\src\ovarian_ai\literature\literature_watcher.py:327
  - `path.write_text("\n".join(lines), encoding="utf-8")`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\src\ovarian_ai\literature\literature_watcher.py:418
  - `path.write_text("\n".join(lines), encoding="utf-8")`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\src\ovarian_ai\literature\literature_watcher.py:450
  - `json_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\src\ovarian_ai\literature\literature_watcher.py:451
  - `refined_path.write_text(json.dumps(refined_records, indent=2, ensure_ascii=False), encoding="utf-8")`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\src\ovarian_ai\report\report_generator.py:39
  - `with path.open("r", encoding="utf-8", newline="") as handle:`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\src\ovarian_ai\report\report_generator.py:208
  - `(report_dir / f"Daily_Ovarian_AI_Target_Report_{suffix}.md").write_text(report, encoding="utf-8")`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\src\ovarian_ai\report\report_generator.py:214
  - `(report_dir / f"Next_Action_Report_{suffix}.md").write_text(next_action_report, encoding="utf-8")`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\src\ovarian_ai\report\report_generator.py:215
  - `(report_dir / "codex_next_tasks.md").write_text(`

## Files needing manual review
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\scripts\check_disk_usage.py:46
  - `log_path.write_text(text, encoding="utf-8")`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\scripts\05_validation\scrna_bcr_gse319733_pipeline.R:41
  - `utils::download.file(url, destfile = destfile, mode = "wb", quiet = TRUE)`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\scripts\05_validation\scrna_bcr_gse319733_pipeline.R:125
  - `utils::write.table(sample_qc, file.path(out_dir, "sample_qc_summary.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\scripts\05_validation\scrna_bcr_gse319733_pipeline.R:138
  - `utils::write.table(key_gene_table, file.path(out_dir, "key_gene_expression_by_tissue.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\scripts\05_validation\scrna_bcr_gse319733_pipeline.R:145
  - `utils::write.table(bcr_summary, file.path(out_dir, "bcr_basic_summary.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\src\ovarian_ai\datasets\dataset_watcher.py:312
  - `path.write_text("\n".join(lines), encoding="utf-8")`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\src\ovarian_ai\datasets\dataset_watcher.py:342
  - `with out_path.open("w", newline="", encoding="utf-8") as handle:`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\src\ovarian_ai\datasets\dataset_watcher.py:346
  - `with refined_path.open("w", newline="", encoding="utf-8") as handle:`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\src\ovarian_ai\literature\literature_watcher.py:327
  - `path.write_text("\n".join(lines), encoding="utf-8")`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\src\ovarian_ai\literature\literature_watcher.py:418
  - `path.write_text("\n".join(lines), encoding="utf-8")`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\src\ovarian_ai\literature\literature_watcher.py:450
  - `json_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\src\ovarian_ai\literature\literature_watcher.py:451
  - `refined_path.write_text(json.dumps(refined_records, indent=2, ensure_ascii=False), encoding="utf-8")`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\src\ovarian_ai\report\report_generator.py:39
  - `with path.open("r", encoding="utf-8", newline="") as handle:`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\src\ovarian_ai\report\report_generator.py:208
  - `(report_dir / f"Daily_Ovarian_AI_Target_Report_{suffix}.md").write_text(report, encoding="utf-8")`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\src\ovarian_ai\report\report_generator.py:214
  - `(report_dir / f"Next_Action_Report_{suffix}.md").write_text(next_action_report, encoding="utf-8")`
- current-directory output write: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\src\ovarian_ai\report\report_generator.py:215
  - `(report_dir / "codex_next_tasks.md").write_text(`

## Recommended fixes
- Route all raw data, processed data, results, cache, and logs through `config/paths.yaml` and `ovarian_ai.utils.paths`.
- Keep network downloads pointed to D-drive raw/cache directories.
- Keep logs under `D:/Ovarian_AI_Target_Factory/results/logs` or another configured D-drive result subdirectory.
- If temporary files become necessary, create them under the configured cache directory.
