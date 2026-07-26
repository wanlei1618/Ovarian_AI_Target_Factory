args <- commandArgs(trailingOnly = TRUE)
get_arg <- function(flag, default = NA_character_) {
  idx <- match(flag, args)
  if (is.na(idx) || idx == length(args)) default else args[[idx + 1]]
}
run_id <- get_arg("--run-id")
if (is.na(run_id) || "--help" %in% args || "-h" %in% args) {
  cat("Usage: Rscript 05_analyze_bcr.R --run-id <RUN_ID>\n")
  quit(status = ifelse(is.na(run_id), 1, 0))
}
.libPaths(unique(c("D:/Ovarian_AI_Target_Factory/R_library", .libPaths())))
suppressPackageStartupMessages({
  library(data.table)
  library(ggplot2)
})
root <- "D:/Ovarian_AI_Target_Factory"
out_dir <- file.path(root, "results", "scrna", "GSE319733", run_id)
manifest <- fread(file.path(out_dir, "sample_manifest.tsv"))
manifest <- manifest[has_vdj == "true"]

shannon <- function(x) {
  if (!length(x) || sum(x) == 0) return(NA_real_)
  p <- x / sum(x)
  -sum(p[p > 0] * log(p[p > 0]))
}
gini <- function(x) {
  if (!length(x) || sum(x) == 0) return(NA_real_)
  x <- sort(as.numeric(x)); n <- length(x)
  (2 * sum(seq_len(n) * x) / (n * sum(x))) - (n + 1) / n
}
pick_col <- function(dt, candidates) {
  hit <- intersect(candidates, names(dt))
  if (length(hit)) hit[[1]] else NA_character_
}

all_contigs <- list()
qc_rows <- list()
for (i in seq_len(nrow(manifest))) {
  row <- manifest[i]
  dt <- fread(row$vdj_contigs)
  prod_col <- pick_col(dt, c("productive", "productive.x"))
  chain_col <- pick_col(dt, c("chain"))
  aa_col <- pick_col(dt, c("cdr3", "cdr3_aa", "cdr3s_aa"))
  raw_clone_col <- pick_col(dt, c("raw_clonotype_id", "clonotype_id"))
  if (!is.na(prod_col)) dt <- dt[tolower(as.character(get(prod_col))) %in% c("true", "t", "yes")]
  if (!is.na(chain_col)) {
    heavy <- dt[get(chain_col) %in% c("IGH", "IGHM", "IGHG", "IGHA", "IGHD", "IGHE")]
    light <- dt[get(chain_col) %in% c("IGK", "IGL")]
  } else {
    heavy <- dt[0]; light <- dt[0]
  }
  if (!is.na(aa_col) && nrow(dt)) {
    cell_col <- pick_col(dt, c("barcode", "cell_id"))
    if (is.na(cell_col)) cell_col <- names(dt)[1]
    heavy_key <- if (nrow(heavy)) heavy[, .(heavy_cdr3 = paste(unique(get(aa_col)), collapse = "|")), by = cell_col] else data.table()
    light_key <- if (nrow(light)) light[, .(light_cdr3 = paste(unique(get(aa_col)), collapse = "|")), by = cell_col] else data.table()
    setnames(heavy_key, cell_col, "barcode", skip_absent = TRUE)
    setnames(light_key, cell_col, "barcode", skip_absent = TRUE)
    canon <- merge(heavy_key, light_key, by = "barcode", all = TRUE)
    canon[is.na(heavy_cdr3), heavy_cdr3 := ""]
    canon[is.na(light_cdr3), light_cdr3 := ""]
    canon[, canonical_clonotype := paste(row$patient_id, heavy_cdr3, light_cdr3, sep = "::")]
  } else if (!is.na(raw_clone_col)) {
    canon <- dt[, .(barcode = seq_len(.N), canonical_clonotype = paste(row$patient_id, get(raw_clone_col), sep = "::"))]
  } else {
    canon <- data.table(barcode = character(), canonical_clonotype = character())
  }
  canon[, `:=`(patient_id = row$patient_id, biological_sample_id = row$biological_sample_id, tissue_code = row$tissue_code)]
  all_contigs[[length(all_contigs) + 1]] <- canon
  counts <- canon[, .N, by = canonical_clonotype]
  qc_rows[[length(qc_rows) + 1]] <- data.table(
    patient_id = row$patient_id,
    biological_sample_id = row$biological_sample_id,
    tissue_code = row$tissue_code,
    valid_bcr_cells = nrow(canon),
    unique_clonotypes = nrow(counts),
    expanded_clonotypes = sum(counts$N > 1),
    shannon_diversity = shannon(counts$N),
    gini_index = gini(counts$N)
  )
}

contigs <- rbindlist(all_contigs, fill = TRUE)
qc <- rbindlist(qc_rows, fill = TRUE)
expansion <- if (nrow(contigs)) contigs[, .N, by = .(patient_id, biological_sample_id, tissue_code, canonical_clonotype)] else data.table()
diversity <- qc
shared <- data.table()
for (patient in unique(contigs$patient_id)) {
  sub <- contigs[patient_id == patient]
  ln <- unique(sub[tissue_code == "LN", canonical_clonotype])
  pt <- unique(sub[tissue_code == "PT", canonical_clonotype])
  both <- intersect(ln, pt)
  if (length(both)) {
    shared <- rbind(shared, data.table(patient_id = patient, canonical_clonotype = both, present_in_LN = TRUE, present_in_PT = TRUE), fill = TRUE)
  }
}
summary <- contigs[, .(total_unique_clonotypes = uniqueN(canonical_clonotype)), by = patient_id]
shared_summary <- if (nrow(summary)) merge(summary, shared[, .(shared_clonotypes = uniqueN(canonical_clonotype)), by = patient_id], by = "patient_id", all.x = TRUE) else data.table()
shared_summary[is.na(shared_clonotypes), shared_clonotypes := 0]
shared_summary[, shared_clonotype_fraction := shared_clonotypes / pmax(total_unique_clonotypes, 1)]

fwrite(qc, file.path(out_dir, "bcr_qc_summary.tsv"), sep = "\t")
fwrite(expansion, file.path(out_dir, "clonotype_expansion_by_sample.tsv"), sep = "\t")
fwrite(diversity, file.path(out_dir, "bcr_diversity_by_patient.tsv"), sep = "\t")
fwrite(shared, file.path(out_dir, "shared_clonotypes_LN_PT.tsv"), sep = "\t")
fwrite(shared_summary, file.path(out_dir, "shared_clonotype_summary_by_patient.tsv"), sep = "\t")
pdf(file.path(out_dir, "clonotype_network.pdf"), width = 7, height = 5)
print(ggplot(shared_summary, aes(patient_id, shared_clonotype_fraction)) + geom_col() + theme_bw())
dev.off()
writeLines(c("# BCR Analysis Summary", "", paste0("- samples_with_vdj: ", nrow(manifest)), paste0("- patients_with_shared_LN_PT_clonotypes: ", sum(shared_summary$shared_clonotypes > 0)), "- clonotypes compared only within the same patient."), file.path(out_dir, "bcr_analysis_summary.md"))
status_json <- sprintf('{\n  "module": "GSE319733_BCR_R",\n  "analysis_status": "COMPLETED",\n  "quality_gate_passed": %s,\n  "row_counts": {"bcr_qc_summary": %d, "shared_clonotypes_LN_PT": %d},\n  "timestamp": "%s",\n  "blocking_reason": ""\n}\n', tolower(as.character(nrow(qc) > 0)), nrow(qc), nrow(shared), as.character(Sys.time()))
writeLines(status_json, file.path(out_dir, "bcr_analysis_status.json"))
cat(out_dir, "\n")
