args <- commandArgs(trailingOnly = TRUE)
if ("--help" %in% args || "-h" %in% args) {
  cat("Usage: Rscript 04_analyze_gex.R --run-id <RUN_ID> [--config <paths.yaml>]\n")
  quit(status = 0)
}
cat("GSE319733 GEX analysis is delegated to gse319733_analysis.py when direct processed matrices are available.\n")
