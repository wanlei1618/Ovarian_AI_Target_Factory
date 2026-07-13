#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
`%||%` <- function(a, b) if (!is.null(a)) a else b
file_arg <- grep("^--file=", commandArgs(FALSE), value = TRUE)
if (length(file_arg) == 0 || is.na(file_arg[1])) {
  script_file <- "scripts/05_validation/scrna_bcr_gse319733_pipeline.R"
} else {
  script_file <- sub("^--file=", "", file_arg[1])
}
project_root <- normalizePath(file.path(dirname(script_file), "..", ".."), winslash = "/", mustWork = FALSE)
utils_path <- file.path(project_root, "R", "utils_paths.R")
if (!file.exists(utils_path)) {
  project_root <- getwd()
  utils_path <- file.path(project_root, "R", "utils_paths.R")
}
source(utils_path)

today <- "2026-07-12"
config_path <- file.path(project_root, "config", "paths.yaml")
dirs <- ensure_project_dirs()
raw_dir <- file.path(dirs$raw, "single_cell", "GSE319733")
out_dir <- file.path(dirs$results, "scrna", "GSE319733")
log_dir <- file.path(dirs$results, "logs")
dir.create(raw_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(log_dir, recursive = TRUE, showWarnings = FALSE)
log_file <- file.path(log_dir, paste0("GSE319733_pipeline_", gsub("-", "", today), ".log"))

log_msg <- function(...) {
  msg <- paste(format(Sys.time(), "%Y-%m-%d %H:%M:%S"), paste(..., collapse = " "))
  cat(msg, "\n", file = log_file, append = TRUE)
}

safe_download <- function(url, destfile) {
  if (file.exists(destfile) && file.info(destfile)$size > 0) {
    log_msg("Skip existing file:", destfile)
    return(TRUE)
  }
  ok <- tryCatch({
    utils::download.file(url, destfile = destfile, mode = "wb", quiet = TRUE)
    TRUE
  }, error = function(e) {
    log_msg("Download failed:", url, conditionMessage(e))
    FALSE
  })
  ok
}

parse_series_matrix <- function(path) {
  if (!file.exists(path)) {
    return(data.frame())
  }
  lines <- tryCatch(readLines(gzfile(path), warn = FALSE), error = function(e) {
    log_msg("Failed reading series matrix:", conditionMessage(e))
    character()
  })
  get_values <- function(prefix) {
    line <- lines[startsWith(lines, prefix)][1]
    if (is.na(line)) return(character())
    parts <- strsplit(line, "\t", fixed = TRUE)[[1]]
    gsub('^"|"$', "", parts[-1])
  }
  accessions <- get_values("!Sample_geo_accession")
  titles <- get_values("!Sample_title")
  sources <- get_values("!Sample_source_name_ch1")
  characteristics <- get_values("!Sample_characteristics_ch1")
  n <- length(accessions)
  if (n == 0) return(data.frame())
  pad <- function(x) {
    length(x) <- n
    x[is.na(x)] <- ""
    x
  }
  text <- paste(pad(titles), pad(sources), pad(characteristics))
  tissue <- ifelse(grepl("lymph|node|tdln|draining", text, ignore.case = TRUE), "tumor-draining lymph node",
                   ifelse(grepl("primary|tumou?r|ovary|ovarian", text, ignore.case = TRUE), "matched primary tumor", "unknown"))
  data.frame(
    sample_id = accessions,
    tissue_type = tissue,
    title = pad(titles),
    source = pad(sources),
    estimated_cell_count = NA,
    detected_gene_count = NA,
    has_GEX = grepl("gene expression|gex|rna|single", text, ignore.case = TRUE),
    has_BCR = grepl("bcr|vdj|immunoglobulin|b cell", text, ignore.case = TRUE),
    file_size = NA,
    stringsAsFactors = FALSE
  )
}

write_placeholder_pdf <- function(path, title, labels) {
  grDevices::pdf(path, width = 8, height = 5)
  on.exit(grDevices::dev.off(), add = TRUE)
  plot.new()
  title(main = title)
  text(0.05, 0.8, paste(labels, collapse = "\n"), adj = c(0, 1), cex = 0.8)
}

series_url <- "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE319nnn/GSE319733/matrix/GSE319733_series_matrix.txt.gz"
series_path <- file.path(raw_dir, "GSE319733_series_matrix.txt.gz")
suppl_url <- "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE319nnn/GSE319733/suppl/"
suppl_html <- file.path(raw_dir, "GSE319733_supplementary_file_list.html")

log_msg("Starting lightweight GSE319733 metadata pipeline")
safe_download(series_url, series_path)
tryCatch({
  html <- readLines(suppl_url, warn = FALSE)
  writeLines(html, suppl_html)
}, error = function(e) log_msg("Supplementary file list read failed:", conditionMessage(e)))

sample_qc <- parse_series_matrix(series_path)
if (nrow(sample_qc) == 0) {
  sample_qc <- data.frame(
    sample_id = character(),
    tissue_type = character(),
    estimated_cell_count = numeric(),
    detected_gene_count = numeric(),
    has_GEX = logical(),
    has_BCR = logical(),
    file_size = numeric(),
    stringsAsFactors = FALSE
  )
}
utils::write.table(sample_qc, file.path(out_dir, "sample_qc_summary.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)

marker_groups <- data.frame(
  cell_type = c("B cell", "plasma cell", "T cell", "myeloid", "malignant epithelial", "endothelial", "fibroblast/CAF"),
  markers = c("MS4A1, CD79A, CD79B, CD74", "MZB1, JCHAIN, XBP1, IGHG1, IGKC", "CD3D, CD3E, TRAC", "LST1, C1QA, C1QB, SPP1, APOE", "EPCAM, KRT8, KRT18, KRT19, MSLN", "PECAM1, VWF", "COL1A1, COL1A2, DCN, ACTA2"),
  status = "metadata-only; expression matrix not parsed in lightweight run",
  stringsAsFactors = FALSE
)
key_genes <- c("MMP14", "CD79A", "MS4A1", "MZB1", "JCHAIN", "IGHG1", "IGKC", "EPCAM", "KRT8", "KRT18", "PTPRC", "SPP1", "CD44", "ITGB1")
key_gene_table <- expand.grid(gene = key_genes, tissue_type = unique(c(sample_qc$tissue_type, "tumor-draining lymph node", "matched primary tumor")), stringsAsFactors = FALSE)
key_gene_table$mean_expression <- NA
key_gene_table$detection_rate <- NA
key_gene_table$note <- "Expression matrix not downloaded/parsed in lightweight metadata run"
utils::write.table(key_gene_table, file.path(out_dir, "key_gene_expression_by_tissue.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)

bcr_summary <- data.frame(
  metric = c("samples_with_BCR_hint", "supplementary_file_list_available", "raw_tar_downloaded"),
  value = c(sum(sample_qc$has_BCR, na.rm = TRUE), file.exists(suppl_html), FALSE),
  stringsAsFactors = FALSE
)
utils::write.table(bcr_summary, file.path(out_dir, "bcr_basic_summary.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)

write_placeholder_pdf(file.path(out_dir, "celltype_marker_dotplot.pdf"), "GSE319733 marker panel status", paste(marker_groups$cell_type, marker_groups$markers, sep = ": "))
write_placeholder_pdf(file.path(out_dir, "mmp14_expression_by_celltype.pdf"), "MMP14 expression by cell type", c("Expression matrix not parsed in this lightweight run.", "Next step: parse approved count matrix if file size is acceptable."))

ln_count <- sum(sample_qc$tissue_type == "tumor-draining lymph node", na.rm = TRUE)
tumor_count <- sum(sample_qc$tissue_type == "matched primary tumor", na.rm = TRUE)
summary_lines <- c(
  "# GSE319733 Initial Summary",
  "",
  "## 1. Data read status",
  if (file.exists(series_path)) "Series matrix metadata was downloaded/read from the D-drive raw data directory." else "Series matrix metadata was not successfully downloaded; see logs.",
  "",
  "## 2. Per-sample basics",
  paste0("- Samples parsed from metadata: ", nrow(sample_qc)),
  paste0("- Tumor-draining lymph node samples inferred: ", ln_count),
  paste0("- Matched primary tumor samples inferred: ", tumor_count),
  "",
  "## 3. LN vs primary tumor separation",
  if (ln_count > 0 && tumor_count > 0) "Metadata suggests LN and primary tumor samples can be separated." else "Metadata is insufficient for confident LN vs primary tumor separation.",
  "",
  "## 4. B cell / plasma cell presence",
  "The study title and BCR hints support a B-cell/plasma-cell immune niche branch, but expression-level confirmation requires approved matrix parsing.",
  "",
  "## 5. MMP14 expression",
  "MMP14 expression could not be assigned to cell types in this lightweight metadata-only run.",
  "",
  "## 6. SPP1 / CD44 / ITGB1 exploration value",
  "These genes remain worth checking after count matrix parsing because they connect myeloid/malignant interaction and adhesion/invasion axes.",
  "",
  "## 7. Mainline suitability",
  "Best treated as an immune-niche branch dataset rather than the primary HGSOC target-discovery backbone.",
  "",
  "## 8. Next steps",
  "- Review supplementary file sizes.",
  "- Approve only the smallest required GEX/BCR matrices for parsing.",
  "- Then compute marker expression and BCR clonotype summaries."
)
writeLines(summary_lines, file.path(out_dir, "GSE319733_initial_summary.md"))
log_msg("Completed lightweight GSE319733 metadata pipeline")
