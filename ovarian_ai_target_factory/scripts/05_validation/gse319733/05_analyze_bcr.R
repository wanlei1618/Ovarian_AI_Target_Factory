args <- commandArgs(trailingOnly = TRUE)
if ("--help" %in% args || "-h" %in% args) {
  cat("Usage: Rscript 05_analyze_bcr.R --run-id <RUN_ID> [--config <paths.yaml>]\n")
  quit(status = 0)
}
cat("GSE319733 BCR analysis is delegated to gse319733_analysis.py when direct VDJ contig files are available.\n")
