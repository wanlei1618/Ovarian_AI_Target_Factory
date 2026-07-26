# Final Execution Report

- run_id: 20260727_000754_a879f8a
- analysis_code_sha: ecbcea14cf30f79eed3109b834346cce36570df0
- results_commit_sha: PENDING
- branch: codex/after-244c94d
- PR URL: pending

## Python/R Environment
- Python: D:/Ovarian_AI_Target_Factory/envs/py313 ({
    "python_version":  "Python 3.13.13",
    "analysis_code_sha":  "a879f8aa0f88a1a1b05f286d3bf7d6281fff2725",
    "en)
- pytest: 29 passed; junit saved to pipeline_qc/pytest.xml
- R: D:/R/R-4.6.1/bin/Rscript.exe; sessionInfo and package check saved under pipeline_qc

## GSE319733 Archive
- GSE319733_RAW.tar size_bytes: 352532480
- GSE319733_RAW.tar sha256: aea75da36ee401f9cd80fdfb0e13158969322bc3868b3cda95444194bdc1d589
- archive_path: D:\Ovarian_AI_Target_Factory\data_raw\single_cell\GSE319733\archives\GSE319733_RAW.tar
- extracted_whitelisted_files: 50
- extracted_file_types: cell_metadata=10, gex_barcodes=10, gex_features=10, gex_matrix=10, vdj_contigs=10
- FASTQ/BAM extracted: no

## GSE319733 GEX
- biological_samples: 10
- paired_patients: P1,P2,P3,P4; LN-only: P5,P6
- QC cells_after_total: 43432
- broad_celltype_counts: B_cell=28728, T_NK=11118, plasma_cell=2558, other=500, myeloid=250, endothelial=240, epithelial=34, fibroblast_CAF=4
- malignant_cell_specificity: INSUFFICIENT_DATA without CNV or author malignant labels

## GSE319733 BCR / Patient Statistics
- BCR status: COMPLETED; {'bcr_qc_summary': 10, 'shared_clonotypes_LN_PT': 5413}
- patient statistics: COMPLETED; paired=P1,P2,P3,P4
- shared_clonotypes_LN_PT rows: 5413

## Candidate Axis
- main_axis_eligibility: NO
- branch_value: B-cell / TDLN immune niche
- SPP1-CD44/ITGB1 evidence: expression co-detection/patient-level association only; no mechanistic validation; malignant receptor specificity insufficient.

## Other GEO Datasets
- GSE337705/GSE337706 status: METADATA_ONLY; donor rows=29
- GSE338829 assay_type: RIP-seq; evidence_type: RNA-binding target evidence; sample_count=4

## Target Factory
- evidence_records rows: 50
- candidate_target_table rows: 7
- RBMS1/NEDD4 source_dataset: GSE338829 only

## D-Drive Paths
- raw: D:\Ovarian_AI_Target_Factory\data_raw
- processed: D:\Ovarian_AI_Target_Factory\data_processed
- results: D:\Ovarian_AI_Target_Factory\results
- cache: D:\Ovarian_AI_Target_Factory\cache

## GitHub Sync Policy
- synced root: D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory\results_synced
- large/raw unsynced: GSE319733_RAW.tar, MTX/barcodes/features, cell-level annotation table, RDS, FASTQ/BAM, cache/logs/secrets
- GitHub only receives lightweight reports/tables/PDFs under ovarian_ai_target_factory/results_synced.
