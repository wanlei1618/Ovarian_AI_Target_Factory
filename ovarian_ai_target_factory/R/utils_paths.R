get_data_root <- function() {
  env_root <- Sys.getenv("OVARIAN_AI_DATA_ROOT", unset = NA)
  if (!is.na(env_root) && nzchar(env_root)) {
    return(normalizePath(env_root, winslash = "/", mustWork = FALSE))
  }

  config_path <- file.path(getwd(), "config", "paths.yaml")
  if (file.exists(config_path)) {
    if (!requireNamespace("yaml", quietly = TRUE)) {
      stop("Package 'yaml' is required to read config/paths.yaml")
    }
    cfg <- yaml::read_yaml(config_path)
    if (!is.null(cfg$data_root) && nzchar(cfg$data_root)) {
      return(normalizePath(cfg$data_root, winslash = "/", mustWork = FALSE))
    }
  }

  if (.Platform$OS.type == "windows" && dir.exists("D:/")) {
    return("D:/Ovarian_AI_Target_Factory")
  }

  if (dir.exists("/mnt/d")) {
    return("/mnt/d/Ovarian_AI_Target_Factory")
  }

  warning("D drive not found. Using ./local_data. Large downloads may occupy the current drive.")
  return(normalizePath("local_data", winslash = "/", mustWork = FALSE))
}

ensure_project_dirs <- function() {
  root <- get_data_root()
  config_path <- file.path(getwd(), "config", "paths.yaml")
  cfg <- list()
  if (file.exists(config_path)) {
    if (!requireNamespace("yaml", quietly = TRUE)) {
      stop("Package 'yaml' is required to read config/paths.yaml")
    }
    cfg <- yaml::read_yaml(config_path)
  }
  configured_path <- function(key, default) {
    value <- cfg[[key]]
    if (!is.null(value) && nzchar(value)) {
      return(normalizePath(value, winslash = "/", mustWork = FALSE))
    }
    return(normalizePath(default, winslash = "/", mustWork = FALSE))
  }
  dirs <- list(
    raw = configured_path("raw_dir", file.path(root, "data_raw")),
    processed = configured_path("processed_dir", file.path(root, "data_processed")),
    results = configured_path("results_dir", file.path(root, "results")),
    cache = configured_path("cache_dir", file.path(root, "cache")),
    logs = configured_path("logs_dir", file.path(root, "logs"))
  )
  forbidden <- c("C:/Users", "C:/ProgramData", "Downloads", "Documents", "AppData")
  for (path in dirs) {
    normalized <- normalizePath(path, winslash = "/", mustWork = FALSE)
    if (startsWith(normalized, "C:/") || any(grepl(paste(forbidden, collapse = "|"), normalized, ignore.case = TRUE))) {
      stop(paste("Refusing to write output under forbidden path:", normalized))
    }
  }
  invisible(lapply(dirs, dir.create, recursive = TRUE, showWarnings = FALSE))
  return(dirs)
}
