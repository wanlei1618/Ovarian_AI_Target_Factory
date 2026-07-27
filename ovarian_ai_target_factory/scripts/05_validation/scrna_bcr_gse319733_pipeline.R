#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
run_id <- Sys.getenv("RUN_ID", unset = "")
if ("--run-id" %in% args) {
  run_id <- args[which(args == "--run-id") + 1]
}
if (!nzchar(run_id)) {
  stop("--run-id is required")
}

script_arg <- grep("^--file=", commandArgs(FALSE), value = TRUE)
script_file <- if (length(script_arg)) sub("^--file=", "", script_arg[1]) else "scripts/05_validation/scrna_bcr_gse319733_pipeline.R"
project_root <- normalizePath(file.path(dirname(script_file), "..", ".."), winslash = "/", mustWork = FALSE)
python_script <- file.path(project_root, "scripts", "05_validation", "gse319733_analysis.py")
cmd <- c(python_script, "--run-id", run_id)
status <- system2("python", cmd)
quit(status = status)
