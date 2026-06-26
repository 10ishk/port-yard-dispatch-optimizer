"""Shared filesystem and runtime configuration."""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
SAMPLE_DATA_DIR = DATA_DIR / "sample"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
DISPATCH_OUTPUT_DIR = OUTPUTS_DIR / "dispatch_plans"
MAP_OUTPUT_DIR = OUTPUTS_DIR / "maps"
REPORT_OUTPUT_DIR = OUTPUTS_DIR / "reports"
SQL_DIR = PROJECT_ROOT / "sql"
SCHEMA_PATH = SQL_DIR / "schema.sql"

DEFAULT_DB_PATH = PROCESSED_DATA_DIR / "dispatch.db"
DEFAULT_RANDOM_SEED = 42
DEFAULT_SHIPMENTS = int(os.getenv("DEFAULT_SHIPMENTS", "120"))
DEFAULT_VEHICLES = int(os.getenv("DEFAULT_VEHICLES", "16"))


def get_database_path() -> Path:
    """Return the configured SQLite database path."""
    configured = os.getenv("DISPATCH_DB_PATH")
    if configured:
        path = Path(configured)
        return path if path.is_absolute() else PROJECT_ROOT / path
    return DEFAULT_DB_PATH


def ensure_project_dirs() -> None:
    """Create runtime folders used by generation, optimization, and exports."""
    for path in [
        RAW_DATA_DIR,
        PROCESSED_DATA_DIR,
        SAMPLE_DATA_DIR,
        DISPATCH_OUTPUT_DIR,
        MAP_OUTPUT_DIR,
        REPORT_OUTPUT_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)

