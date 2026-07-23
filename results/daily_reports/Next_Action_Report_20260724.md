# Next Action Report: 2026-07-24

## 1. Approved downloads today
- GSE319733: Tumor-draining lymph nodes in ovarian cancer lack germinal centers but harbor tumor-reactive memory B cells clonally linked to intra-tumoral B cells
  - action: approve_download
  - reason: high-priority ovarian cancer single-cell RNA-seq/BCR dataset involving tumor-draining lymph nodes and matched primary tumors; suitable for immune niche branch analysis
  - branch: B-cell / tumor-draining lymph node immune niche in ovarian cancer

## 2. Deferred downloads today
- GSE338829: RBMS1 Suppresses Ovarian Cancer Malignant Progression Through Post-transcriptional regulation expression of NEDD4
  - action: needs_manual_review
  - reason: No curated action rule matched; review metadata before any download.
  - branch: 
- GSE337706: Exploring Platelet-Covered and Naked Circulating Tumor Cells: A Single-Cell Transcriptomic Perspective [scRNA-seq Singleron]
  - action: defer
  - reason: Potentially useful high-dimensional dataset; defer until size and metadata are reviewed.
  - branch: 

## 3. Metadata-only datasets today
- GSE262172: GSK-J4 treatment in ovarian cancer cell lines (ATAC-Seq)
  - action: metadata_only
  - reason: ATAC-seq dataset in ovarian cancer cell lines; RAW file is relatively large and ATAC pipeline is not yet part of MVP; defer large download
  - branch: chromatin accessibility and epigenetic drug response
- GSE310580: DNA Methylation Profiling Enables Subclassification of Mucinous Ovarian Carcinoma and Distinguishes It from Extraovarian Mucinous Metastases
  - action: metadata_only
  - reason: mucinous ovarian carcinoma methylation classifier dataset; useful as a diagnostic ML branch but not primary HGSOC target discovery workflow
  - branch: mucinous ovarian carcinoma methylation classification

## 4. Excluded or downgraded literature today
- Development and validation of a miRNA-based prognostic model for high-grade serous ovarian cancer: a retrospective cohort study.
  - PMID: 42291842
  - priority: medium-low
  - exclusion_status: downgrade
  - reason: non-coding RNA signature without strong mechanistic or multimodal validation

## 5. False positive literature today
- None

## 6. Literature still worth manual review
- None

## 7. New branch directions today
- B-cell / tumor-draining lymph node immune niche in ovarian cancer: use GSE319733 for metadata-first lightweight exploration.
- Chromatin accessibility and epigenetic drug response: keep GSE262172 as metadata-only until ATAC workflow is approved.
- Mucinous ovarian carcinoma methylation classification: keep GSE310580 as a diagnostic ML branch, not the current HGSOC mainline.

## 8. Next Codex tasks
- Run the GSE319733 lightweight metadata parser and inspect supplementary file sizes.
- If file sizes are acceptable, parse only approved GEX/BCR matrices from D-drive raw data.
- Improve PubMed filtering with manual labels from the audit report.
- Add duplicate handling and accession extraction for literature records.

## 9. Questions for ChatGPT judgment
- Should GSE319733 become an immune-niche side branch or feed the main target discovery score?
- Which retained papers deserve manual reading first?
- Are SPP1/CD44/ITGB1 worth prioritizing as an immune-niche invasion axis after GSE319733 parsing?

## 10. Path compliance summary
- Raw data root: D:/Ovarian_AI_Target_Factory/data_raw
- Processed data root: D:/Ovarian_AI_Target_Factory/data_processed
- Results root: D:/Ovarian_AI_Target_Factory/results
- Cache root: D:/Ovarian_AI_Target_Factory/cache
- This report is generated under D:/Ovarian_AI_Target_Factory/results/daily_reports.
- No C-drive output path is approved.
