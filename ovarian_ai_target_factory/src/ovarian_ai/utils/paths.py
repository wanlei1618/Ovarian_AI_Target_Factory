from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Any

import yaml


FORBIDDEN_PATH_MARKERS = (
    "downloads",
    "documents",
    "appdata",
    "programdata",
)


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_config(config_path: Path | None = None) -> dict[str, Any]:
    path = config_path or get_project_root() / "config" / "paths.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def get_data_root(config_path: Path | None = None) -> Path:
    env_root = os.environ.get("OVARIAN_AI_DATA_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    cfg = _read_config(config_path)
    if cfg.get("data_root"):
        return Path(cfg["data_root"]).expanduser().resolve()

    if platform.system().lower().startswith("win") and Path("D:/").exists():
        return Path("D:/Ovarian_AI_Target_Factory").resolve()

    if Path("/mnt/d").exists():
        return Path("/mnt/d/Ovarian_AI_Target_Factory").resolve()

    fallback = get_project_root() / "local_data"
    print(f"[WARNING] D drive not found. Using fallback path: {fallback}")
    return fallback.resolve()


def _configured_path(cfg: dict[str, Any], key: str, default: Path) -> Path:
    value = cfg.get(key)
    if value:
        return Path(value).expanduser().resolve()
    return default.resolve()


def validate_output_path(path: Path) -> None:
    resolved = path.resolve()
    parts = {part.lower() for part in resolved.parts}
    if resolved.drive.upper() == "C:":
        raise RuntimeError(f"Refusing to write data/cache/result output to C drive: {resolved}")
    blocked = sorted(parts.intersection(FORBIDDEN_PATH_MARKERS))
    if blocked:
        raise RuntimeError(f"Refusing to write output under forbidden directory {blocked}: {resolved}")


def ensure_subdirs(config_path: Path | None = None) -> dict[str, Path]:
    cfg = _read_config(config_path)
    root = get_data_root(config_path)
    subdirs = {
        "root": root,
        "raw": _configured_path(cfg, "raw_dir", root / "data_raw"),
        "processed": _configured_path(cfg, "processed_dir", root / "data_processed"),
        "results": _configured_path(cfg, "results_dir", root / "results"),
        "cache": _configured_path(cfg, "cache_dir", root / "cache"),
        "logs": _configured_path(cfg, "logs_dir", root / "logs"),
    }
    for key, path in subdirs.items():
        if key != "root":
            validate_output_path(path)
            path.mkdir(parents=True, exist_ok=True)
    return subdirs


def daily_report_dir(run_date: str, config_path: Path | None = None) -> Path:
    dirs = ensure_subdirs(config_path)
    outdir = dirs["results"] / "daily_reports" / run_date
    validate_output_path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "logs").mkdir(parents=True, exist_ok=True)
    return outdir


def daily_reports_root(config_path: Path | None = None) -> Path:
    dirs = ensure_subdirs(config_path)
    outdir = dirs["results"] / "daily_reports"
    validate_output_path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "logs").mkdir(parents=True, exist_ok=True)
    return outdir


def assert_not_c_data_path(path: Path) -> None:
    validate_output_path(path)
