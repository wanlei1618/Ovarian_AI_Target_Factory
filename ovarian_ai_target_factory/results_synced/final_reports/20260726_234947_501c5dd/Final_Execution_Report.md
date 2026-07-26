# Final Execution Report

- run_id: 20260726_234947_501c5dd
- git_branch: codex/next-analysis
- local_git_sha: 0a85d2f229053a3a14c5513c661966d7d4b10cd9
- remote_branch: codex/improve-after-20260724
- remote_main_note: GitHub sync is performed with lightweight result copies; no force push is used.

## Module Status
- Phase 0 environment / Rscript / disk / Git precheck: COMPLETED
- Phase 1 pipeline realism and report logic: COMPLETED_WITH_WARNINGS
- Phase 2 GSE337706/GSE338829 feasibility: COMPLETED_WITH_WARNINGS
- Phase 2 GSE319733 GEX/BCR analysis: BLOCKED
- Phase 3 minimal target evidence factory: COMPLETED_WITH_WARNINGS
- Phase 4 lightweight GitHub sync: RUNNING_OR_PENDING

## Completed Modules
- Separated raw GEO hits, daily newly detected datasets, curated dataset registry, and refined dataset registry.
- Fixed curated GSE262172 modality to ATAC-seq.
- Updated daily report logic to use refined literature/dataset outputs.
- Reclassified GSE337706 as ovarian liquid biopsy / platelet-coated CTC branch.
- Checked GSE338829 as RBMS1-NEDD4 perturbation-validation feasibility branch.
- Created real GSE319733 supplementary file inventory from GEO.
- Added target evidence table with NOT_TESTED / NEGATIVE / INSUFFICIENT_DATA semantics.
- Added lightweight GitHub sync script and manifests.

## Incomplete or Blocked Modules
- GSE319733 expression/BCR matrix parsing is BLOCKED unless RAW.tar download is manually approved. GEO filelist names processed files, but individual files return 404 outside RAW.tar.
- pytest was requested but is not installed in the current Python 3.7 environment; direct standard-library test execution was used.
- No Target Cards generated because no candidate has two independent evidence sources plus patient-level support.

## GSE319733 Suitability for SPP1 Main Axis
- main_axis_eligibility: NO
- reason: processed expression/VDJ matrices were not parsed because direct processed file URLs returned 404 and RAW.tar default download is disallowed.
- branch_value: B-cell / tumor-draining lymph-node immune niche.

## SPP1-CD44/ITGB1 Evidence
- new_support: NOT_TESTED
- contradictory_evidence: NOT_TESTED
- untested_items: patient-level expression, malignant epithelial specificity, myeloid SPP1 source, CD44/ITGB1 receptor localization, paired pseudobulk support.

## Candidate Ranking
- See `candidate_target_table.tsv` under target_factory.
- SPP1, CD44, ITGB1, MMP14 are retained as exploratory inputs only; no high-score assignment was made.

## Key D-Drive Paths
- raw data: D:\Ovarian_AI_Target_Factory\data_raw
- processed data: D:\Ovarian_AI_Target_Factory\data_processed
- results: D:\Ovarian_AI_Target_Factory\results
- cache: D:\Ovarian_AI_Target_Factory\cache
- logs: D:\Ovarian_AI_Target_Factory\logs

## GitHub Sync Directories
- pipeline_qc: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\results_synced\pipeline_qc\20260726_234947_501c5dd
- daily_reports: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\results_synced\daily_reports\20260726_234947_501c5dd
- scrna/GSE319733: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\results_synced\scrna\GSE319733\20260726_234947_501c5dd
- dataset_feasibility: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\results_synced\dataset_feasibility\20260726_234947_501c5dd
- target_factory: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\results_synced\target_factory\20260726_234947_501c5dd
- final_reports: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\results_synced\final_reports\20260726_234947_501c5dd

## Unsynced Large Files
- RAW.tar and all large raw sequencing formats are excluded by policy.
- See `excluded_from_sync.tsv` after sync for file-level details.

## Next Minimal Tasks
- Decide whether downloading GSE319733_RAW.tar (336 MB) is allowed for processed matrix extraction.
- If approved, extract only processed MTX/barcodes/features/VDJ contigs to D-drive raw data and rerun GSE319733 analysis.
- Add one independent dataset before any Target Card generation.
