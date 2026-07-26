args <- commandArgs(trailingOnly = TRUE)
get_arg <- function(flag, default = NA_character_) {
  idx <- match(flag, args)
  if (is.na(idx) || idx == length(args)) default else args[[idx + 1]]
}
run_id <- get_arg("--run-id")
if (is.na(run_id) || "--help" %in% args || "-h" %in% args) {
  cat("Usage: Rscript 06_patient_level_statistics.R --run-id <RUN_ID>\n")
  quit(status = ifelse(is.na(run_id), 1, 0))
}
.libPaths(unique(c("D:/Ovarian_AI_Target_Factory/R_library", .libPaths())))
suppressPackageStartupMessages({
  library(data.table)
  library(ggplot2)
})
root <- "D:/Ovarian_AI_Target_Factory"
out_dir <- file.path(root, "results", "scrna", "GSE319733", run_id)
cells <- fread(file.path(out_dir, "celltype_annotation.tsv"))
keys <- fread(file.path(out_dir, "key_gene_expression_by_patient.tsv"))

props <- cells[, .N, by = .(patient_id, tissue_code, broad_celltype)]
totals <- cells[, .(total_cells = .N), by = .(patient_id, tissue_code)]
props <- merge(props, totals, by = c("patient_id", "tissue_code"))
props[, proportion := N / total_cells]
paired_patients <- intersect(props[tissue_code == "LN", unique(patient_id)], props[tissue_code == "PT", unique(patient_id)])
paired_patients <- intersect(paired_patients, c("P1", "P2", "P3", "P4"))
paired <- props[patient_id %in% paired_patients]

comparison <- data.table()
for (ct in unique(paired$broad_celltype)) {
  wide <- dcast(paired[broad_celltype == ct], patient_id ~ tissue_code, value.var = "proportion", fill = 0)
  if (all(c("LN", "PT") %in% names(wide)) && nrow(wide) >= 2) {
    delta <- wide$LN - wide$PT
    p <- tryCatch(t.test(wide$LN, wide$PT, paired = TRUE)$p.value, error = function(e) NA_real_)
    comparison <- rbind(comparison, data.table(broad_celltype = ct, paired_patient_count = nrow(wide), mean_LN = mean(wide$LN), mean_PT = mean(wide$PT), effect_size_LN_minus_PT = mean(delta), p_value = p), fill = TRUE)
  }
}
comparison[, fdr := p.adjust(p_value, method = "BH")]
comparison[, patient_consistency := ifelse(effect_size_LN_minus_PT >= 0, "LN_ge_PT", "PT_gt_LN")]

pseudobulk_one <- function(cell_filter, outfile) {
  sub <- keys[cell_type %in% cell_filter & patient_id %in% paired_patients]
  res <- data.table()
  for (g in unique(sub$gene)) {
    wide <- dcast(sub[gene == g], patient_id + cell_type ~ tissue, value.var = "mean_expression", fun.aggregate = mean, fill = NA_real_)
    if (all(c("LN", "PT") %in% names(wide)) && nrow(wide) >= 2) {
      delta <- wide$LN - wide$PT
      p <- tryCatch(t.test(wide$LN, wide$PT, paired = TRUE)$p.value, error = function(e) NA_real_)
      res <- rbind(res, data.table(gene = g, cell_type_group = paste(cell_filter, collapse = ";"), paired_patient_count = nrow(wide), mean_LN = mean(wide$LN, na.rm = TRUE), mean_PT = mean(wide$PT, na.rm = TRUE), effect_size_LN_minus_PT = mean(delta, na.rm = TRUE), p_value = p), fill = TRUE)
    }
  }
  if (nrow(res)) res[, fdr := p.adjust(p_value, method = "BH")]
  fwrite(res, file.path(out_dir, outfile), sep = "\t")
  res
}
bcell <- pseudobulk_one(c("B_cell", "plasma_cell"), "pseudobulk_Bcell_LN_vs_PT.tsv")
myeloid <- pseudobulk_one(c("myeloid"), "pseudobulk_myeloid_LN_vs_PT.tsv")

consistency <- comparison[, .(paired_patient_count = max(paired_patient_count), consistent_direction_count = sum(patient_consistency == patient_consistency[1]), dominant_direction = patient_consistency[1]), by = broad_celltype]
fwrite(props, file.path(out_dir, "celltype_proportions_by_patient.tsv"), sep = "\t")
fwrite(comparison, file.path(out_dir, "paired_celltype_comparison.tsv"), sep = "\t")
fwrite(consistency, file.path(out_dir, "patient_consistency_summary.tsv"), sep = "\t")
axis_genes <- c("SPP1", "CD44", "ITGB1", "MMP14", "CD209", "C1QA", "C1QB", "C1QC")
axis_records <- data.table()
for (g in axis_genes) {
  sub <- keys[gene == g]
  for (ct in unique(sub$cell_type)) {
    wide <- dcast(sub[cell_type == ct & patient_id %in% paired_patients], patient_id ~ tissue, value.var = "detection_rate", fun.aggregate = mean, fill = NA_real_)
    if (all(c("LN", "PT") %in% names(wide)) && nrow(wide) >= 2) {
      delta <- wide$LN - wide$PT
      p <- tryCatch(t.test(wide$LN, wide$PT, paired = TRUE)$p.value, error = function(e) NA_real_)
      status <- ifelse(mean(wide$LN, na.rm = TRUE) >= 0.05 || mean(wide$PT, na.rm = TRUE) >= 0.05, "SUPPORTED", "NEGATIVE")
      axis_records <- rbind(axis_records, data.table(axis = "SPP1-CD44/ITGB1 immune niche", gene = g, patient_id = "P1-P4", tissue = "paired_LN_PT", cell_type = ct, evidence_status = status, direction = ifelse(mean(delta, na.rm = TRUE) >= 0, "LN_ge_PT", "PT_gt_LN"), effect_size = mean(delta, na.rm = TRUE), p_value = p, fdr = NA_real_, detection_rate = mean(c(wide$LN, wide$PT), na.rm = TRUE), mean_expression = NA_real_, sample_count = nrow(wide) * 2, patient_count = nrow(wide), evidence_level = "patient_level_expression", result_path = file.path(out_dir, "key_gene_expression_by_patient.tsv"), reason = "P1-P4 paired patient-level detection comparison"), fill = TRUE)
    }
  }
}
if (nrow(axis_records)) axis_records[, fdr := p.adjust(p_value, method = "BH")]
fwrite(axis_records, file.path(out_dir, "candidate_axis_evidence.tsv"), sep = "\t")
pdf(file.path(out_dir, "paired_effect_plots.pdf"), width = 7, height = 5)
print(ggplot(comparison, aes(broad_celltype, effect_size_LN_minus_PT, fill = broad_celltype)) + geom_col() + theme_bw() + theme(axis.text.x = element_text(angle = 45, hjust = 1)))
dev.off()
status_json <- sprintf('{\n  "module": "GSE319733_patient_statistics_R",\n  "analysis_status": "COMPLETED",\n  "quality_gate_passed": %s,\n  "row_counts": {"celltype_proportions_by_patient": %d, "paired_celltype_comparison": %d},\n  "paired_patients": "%s",\n  "timestamp": "%s",\n  "blocking_reason": ""\n}\n', tolower(as.character(nrow(comparison) > 0)), nrow(props), nrow(comparison), paste(paired_patients, collapse = ","), as.character(Sys.time()))
writeLines(status_json, file.path(out_dir, "patient_statistics_status.json"))
cat(out_dir, "\n")
