args <- commandArgs(trailingOnly = TRUE)
if ("--help" %in% args || "-h" %in% args) {
  cat("Usage: Rscript 06_patient_level_statistics.R --run-id <RUN_ID> [--config <paths.yaml>]\n")
  quit(status = 0)
}
cat("Patient-level statistics require parsed GEX/BCR matrices and are skipped when analysis_status is not COMPLETED.\n")
