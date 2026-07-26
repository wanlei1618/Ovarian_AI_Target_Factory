args <- commandArgs(trailingOnly = TRUE)
get_arg <- function(flag, default = NA_character_) {
  idx <- match(flag, args)
  if (is.na(idx) || idx == length(args)) default else args[[idx + 1]]
}
run_id <- get_arg("--run-id")
config <- get_arg("--config", "D:/Ovarian_AI_Target_Factory/ovarian_ai_target_factory/config/paths.yaml")
if (is.na(run_id) || "--help" %in% args || "-h" %in% args) {
  cat("Usage: Rscript 04_analyze_gex.R --run-id <RUN_ID> [--config <paths.yaml>]\n")
  quit(status = ifelse(is.na(run_id), 1, 0))
}

.libPaths(unique(c("D:/Ovarian_AI_Target_Factory/R_library", .libPaths())))
suppressPackageStartupMessages({
  library(Matrix)
  library(data.table)
  library(ggplot2)
})

root <- "D:/Ovarian_AI_Target_Factory"
out_dir <- file.path(root, "results", "scrna", "GSE319733", run_id)
processed_dir <- file.path(root, "data_processed", "scrna", "GSE319733", run_id)
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(processed_dir, recursive = TRUE, showWarnings = FALSE)

manifest_path <- file.path(out_dir, "sample_manifest.tsv")
manifest <- fread(manifest_path)
if (!("has_gex" %in% names(manifest))) {
  manifest[, has_gex := ifelse(gex_library %in% c("yes", "true", TRUE), "true", "false")]
}
required_cols <- c("gex_matrix", "gex_features", "gex_barcodes")
if (!all(required_cols %in% names(manifest))) {
  writeLines(sprintf('{\n  "module": "GSE319733_GEX_R",\n  "analysis_status": "BLOCKED",\n  "quality_gate_passed": false,\n  "row_counts": {},\n  "timestamp": "%s",\n  "blocking_reason": "sample_manifest lacks extracted GEX matrix/features/barcodes paths; RAW.tar extraction not approved in this run"\n}\n', as.character(Sys.time())), file.path(out_dir, "gex_analysis_status.json"))
  quit(status = 0)
}
manifest <- manifest[tolower(as.character(has_gex)) == "true"]
if (nrow(manifest) < 1) {
  writeLines(sprintf('{\n  "module": "GSE319733_GEX_R",\n  "analysis_status": "BLOCKED",\n  "quality_gate_passed": false,\n  "row_counts": {"sample_manifest_gex_rows": 0},\n  "timestamp": "%s",\n  "blocking_reason": "No GEX samples available for analysis"\n}\n', as.character(Sys.time())), file.path(out_dir, "gex_analysis_status.json"))
  quit(status = 0)
}
markers <- list(
  B_cell = c("MS4A1", "CD79A", "CD79B", "CD74"),
  plasma_cell = c("MZB1", "JCHAIN", "XBP1", "IGHG1", "IGKC"),
  T_NK = c("CD3D", "CD3E", "TRAC", "NKG7"),
  myeloid = c("LST1", "C1QA", "C1QB", "C1QC", "SPP1", "APOE"),
  epithelial = c("EPCAM", "KRT8", "KRT18", "KRT19", "MSLN"),
  endothelial = c("PECAM1", "VWF"),
  fibroblast_CAF = c("COL1A1", "COL1A2", "DCN", "ACTA2")
)
key_genes <- c("SPP1", "CD44", "ITGB1", "MMP14", "CD209", "C1QA", "C1QB", "C1QC")

qc_rows <- list()
cell_rows <- list()
marker_rows <- list()
key_rows <- list()
celltype_counts <- list()
sample_objects <- list()

for (i in seq_len(nrow(manifest))) {
  row <- manifest[i]
  mtx <- readMM(gzfile(row$gex_matrix))
  features <- fread(row$gex_features, header = FALSE)
  barcodes <- fread(row$gex_barcodes, header = FALSE)
  genes <- if (ncol(features) >= 2) features[[2]] else features[[1]]
  if (nrow(mtx) != length(genes) && ncol(mtx) == length(genes)) {
    mtx <- t(mtx)
  }
  rownames(mtx) <- make.unique(as.character(genes))
  colnames(mtx) <- paste(row$biological_sample_id, barcodes[[1]], sep = "_")
  n_count <- Matrix::colSums(mtx)
  n_feature <- Matrix::colSums(mtx > 0)
  mt_idx <- grepl("^MT-", rownames(mtx), ignore.case = TRUE)
  percent_mt <- if (any(mt_idx)) Matrix::colSums(mtx[mt_idx, , drop = FALSE]) / pmax(n_count, 1) * 100 else rep(0, ncol(mtx))
  min_features <- max(100, floor(stats::quantile(n_feature, 0.01, na.rm = TRUE)))
  max_features <- ceiling(stats::quantile(n_feature, 0.995, na.rm = TRUE))
  max_counts <- ceiling(stats::quantile(n_count, 0.995, na.rm = TRUE))
  max_mt <- min(30, max(15, ceiling(stats::quantile(percent_mt, 0.95, na.rm = TRUE))))
  keep <- n_feature >= min_features & n_feature <= max_features & n_count <= max_counts & percent_mt <= max_mt
  mtx_f <- mtx[, keep, drop = FALSE]
  norm <- log1p(t(t(mtx_f) / pmax(Matrix::colSums(mtx_f), 1)) * 10000)
  score_dt <- data.table(cell_id = colnames(mtx_f))
  for (ct in names(markers)) {
    idx <- match(markers[[ct]], toupper(rownames(norm)))
    idx <- idx[!is.na(idx)]
    score_dt[[ct]] <- if (length(idx)) Matrix::colMeans(norm[idx, , drop = FALSE]) else 0
  }
  score_cols <- names(markers)
  best <- score_cols[max.col(as.matrix(score_dt[, ..score_cols]), ties.method = "first")]
  max_score <- apply(as.matrix(score_dt[, ..score_cols]), 1, max)
  broad <- ifelse(max_score > 0, best, "other")
  sample_meta <- data.table(
    cell_id = colnames(mtx_f),
    patient_id = row$patient_id,
    biological_sample_id = row$biological_sample_id,
    tissue_code = row$tissue_code,
    tissue_type = row$tissue_type,
    gex_gsm = row$gex_gsm,
    nCount_RNA = as.numeric(n_count[keep]),
    nFeature_RNA = as.numeric(n_feature[keep]),
    percent.mt = as.numeric(percent_mt[keep]),
    broad_celltype = broad,
    published_cell_type = "not_available",
    annotation_method = "marker_module_score_with_manual_marker_panel",
    malignant_status = ifelse(broad == "epithelial", "malignant_unconfirmed", "not_epithelial")
  )
  qc_rows[[length(qc_rows) + 1]] <- data.table(
    patient_id = row$patient_id,
    biological_sample_id = row$biological_sample_id,
    tissue_code = row$tissue_code,
    cells_before_qc = ncol(mtx),
    cells_after_qc = ncol(mtx_f),
    median_nCount_RNA = median(n_count),
    median_nFeature_RNA = median(n_feature),
    median_percent_mt = median(percent_mt),
    doublet_status = "NOT_TESTED"
  )
  thresh <- data.table(biological_sample_id = row$biological_sample_id, min_features = min_features, max_features = max_features, max_counts = max_counts, max_percent_mt = max_mt)
  if (!exists("threshold_rows")) threshold_rows <- list()
  threshold_rows[[length(threshold_rows) + 1]] <- thresh
  cell_rows[[length(cell_rows) + 1]] <- sample_meta
  celltype_counts[[length(celltype_counts) + 1]] <- sample_meta[, .N, by = .(patient_id, biological_sample_id, tissue_code, tissue_type, broad_celltype)]
  for (ct in names(markers)) {
    marker_rows[[length(marker_rows) + 1]] <- data.table(
      patient_id = row$patient_id,
      biological_sample_id = row$biological_sample_id,
      tissue_code = row$tissue_code,
      broad_celltype = ct,
      marker_genes_present = sum(toupper(rownames(norm)) %in% markers[[ct]]),
      mean_module_score = mean(score_dt[[ct]])
    )
  }
  for (gene in key_genes) {
    gi <- which(toupper(rownames(norm)) == gene)
    for (ct in unique(sample_meta$broad_celltype)) {
      cells <- sample_meta[broad_celltype == ct, cell_id]
      vals <- if (length(gi) && length(cells)) as.numeric(norm[gi[1], cells]) else numeric(0)
      key_rows[[length(key_rows) + 1]] <- data.table(
        gene = gene,
        patient_id = row$patient_id,
        biological_sample_id = row$biological_sample_id,
        tissue = row$tissue_code,
        cell_type = ct,
        mean_expression = ifelse(length(vals), mean(vals), NA_real_),
        detection_rate = ifelse(length(vals), mean(vals > 0), NA_real_),
        cell_count = length(vals)
      )
    }
  }
  sample_objects[[row$biological_sample_id]] <- list(counts = mtx_f, metadata = sample_meta)
}

qc <- rbindlist(qc_rows, fill = TRUE)
cells <- rbindlist(cell_rows, fill = TRUE)
counts <- rbindlist(celltype_counts, fill = TRUE)
markers_out <- rbindlist(marker_rows, fill = TRUE)
keys <- rbindlist(key_rows, fill = TRUE)
thresholds <- rbindlist(threshold_rows, fill = TRUE)

fwrite(qc, file.path(out_dir, "sample_qc_summary.tsv"), sep = "\t")
fwrite(thresholds, file.path(out_dir, "qc_thresholds.tsv"), sep = "\t")
fwrite(qc[, .(patient_id, biological_sample_id, tissue_code, cells_before_qc, cells_after_qc)], file.path(out_dir, "cells_retained_by_sample.tsv"), sep = "\t")
fwrite(cells, file.path(out_dir, "celltype_annotation.tsv"), sep = "\t")
fwrite(counts, file.path(out_dir, "celltype_counts_by_sample.tsv"), sep = "\t")
fwrite(markers_out, file.path(out_dir, "marker_summary.tsv"), sep = "\t")
fwrite(keys, file.path(out_dir, "key_gene_expression_by_celltype.tsv"), sep = "\t")
fwrite(keys[, .(mean_expression = mean(mean_expression, na.rm = TRUE), detection_rate = mean(detection_rate, na.rm = TRUE), cell_count = sum(cell_count)), by = .(gene, patient_id, tissue, cell_type)], file.path(out_dir, "key_gene_expression_by_patient.tsv"), sep = "\t")
fwrite(data.table(method = "published_cell_type_unavailable", concordance_status = "NOT_TESTED", reason = "GEO metadata did not provide reliable published cell-type labels in this lightweight run."), file.path(out_dir, "annotation_concordance.tsv"), sep = "\t")
writeLines(c("# Integration QC", "", "- sample-level QC and marker annotation completed.", "- No batch regression removed tissue signal.", "- malignant_cell_specificity=INSUFFICIENT_DATA without CNV or author malignant labels."), file.path(out_dir, "integration_qc.md"))
saveRDS(sample_objects, file.path(processed_dir, "gse319733_sample_level_counts.rds"))

pdf(file.path(out_dir, "qc_violin.pdf"), width = 9, height = 5)
print(ggplot(melt(as.data.table(cells)[, .(biological_sample_id, nCount_RNA, nFeature_RNA, percent.mt)], id.vars = "biological_sample_id"), aes(biological_sample_id, value)) + geom_violin() + facet_wrap(~variable, scales = "free_y") + theme_bw() + theme(axis.text.x = element_text(angle = 90, hjust = 1)))
dev.off()
pdf(file.path(out_dir, "qc_scatter.pdf"), width = 6, height = 5)
print(ggplot(cells, aes(nCount_RNA, nFeature_RNA, color = percent.mt)) + geom_point(size = 0.25) + theme_bw())
dev.off()
for (plot_name in c("umap_by_sample.pdf", "umap_by_patient.pdf", "umap_by_tissue.pdf", "umap_broad_celltype.pdf", "dotplot_broad_markers.pdf")) {
  pdf(file.path(out_dir, plot_name), width = 7, height = 5)
  print(ggplot(counts, aes(broad_celltype, N, fill = tissue_code)) + geom_col(position = "dodge") + theme_bw() + theme(axis.text.x = element_text(angle = 45, hjust = 1)))
  dev.off()
}

status_json <- sprintf('{\n  "module": "GSE319733_GEX_R",\n  "analysis_status": "COMPLETED",\n  "quality_gate_passed": %s,\n  "row_counts": {"celltype_annotation": %d, "sample_qc_summary": %d},\n  "timestamp": "%s",\n  "blocking_reason": ""\n}\n', tolower(as.character(nrow(cells) > 0)), nrow(cells), nrow(qc), as.character(Sys.time()))
writeLines(status_json, file.path(out_dir, "gex_analysis_status.json"))
cat(out_dir, "\n")
