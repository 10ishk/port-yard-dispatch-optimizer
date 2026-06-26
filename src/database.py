"""SQLite persistence helpers for optimizer inputs and outputs."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.config import SCHEMA_PATH, ensure_project_dirs, get_database_path


BASE_TABLES = ("nodes", "vehicles", "shipments")
OUTPUT_TABLES = (
    "dispatch_plan",
    "route_summary",
    "unassigned_shipments",
    "optimization_runs",
)


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with row dictionaries enabled."""
    ensure_project_dirs()
    path = db_path or get_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(db_path: Path | None = None) -> Path:
    """Create the database schema if it does not already exist."""
    ensure_project_dirs()
    path = db_path or get_database_path()
    with connect(path) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return path


def replace_table(
    table_name: str,
    frame: pd.DataFrame,
    db_path: Path | None = None,
    *,
    clear_first: bool = True,
) -> None:
    """Replace table rows while preserving the declared SQLite schema."""
    initialize_database(db_path)
    with connect(db_path) as connection:
        if clear_first:
            connection.execute(f"DELETE FROM {table_name}")
        frame.to_sql(table_name, connection, if_exists="append", index=False)


def write_base_dataset(
    shipments: pd.DataFrame,
    vehicles: pd.DataFrame,
    nodes: pd.DataFrame,
    db_path: Path | None = None,
) -> Path:
    """Persist base optimization inputs to SQLite."""
    path = initialize_database(db_path)
    with connect(path) as connection:
        for table_name in [*OUTPUT_TABLES, *BASE_TABLES]:
            connection.execute(f"DELETE FROM {table_name}")
        nodes.to_sql("nodes", connection, if_exists="append", index=False)
        vehicles.to_sql("vehicles", connection, if_exists="append", index=False)
        shipments.to_sql("shipments", connection, if_exists="append", index=False)
    return path


def write_optimization_outputs(
    dispatch_plan: pd.DataFrame,
    route_summary: pd.DataFrame,
    unassigned_shipments: pd.DataFrame,
    optimization_run: pd.DataFrame,
    db_path: Path | None = None,
) -> Path:
    """Persist the latest optimizer result to SQLite."""
    path = initialize_database(db_path)
    with connect(path) as connection:
        for table_name in OUTPUT_TABLES:
            connection.execute(f"DELETE FROM {table_name}")
        dispatch_plan.to_sql("dispatch_plan", connection, if_exists="append", index=False)
        route_summary.to_sql("route_summary", connection, if_exists="append", index=False)
        unassigned_shipments.to_sql(
            "unassigned_shipments", connection, if_exists="append", index=False
        )
        optimization_run.to_sql(
            "optimization_runs", connection, if_exists="append", index=False
        )
    return path


def load_table(table_name: str, db_path: Path | None = None) -> pd.DataFrame:
    """Load a table into a DataFrame, returning an empty frame if missing."""
    path = initialize_database(db_path)
    with connect(path) as connection:
        try:
            return pd.read_sql_query(f"SELECT * FROM {table_name}", connection)
        except pd.errors.DatabaseError:
            return pd.DataFrame()


def has_input_data(db_path: Path | None = None) -> bool:
    """Return whether the database has base shipment, vehicle, and node rows."""
    path = initialize_database(db_path)
    with connect(path) as connection:
        counts: list[int] = []
        for table_name in BASE_TABLES:
            row = connection.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
            counts.append(int(row["count"]))
    return all(count > 0 for count in counts)


def table_counts(table_names: Iterable[str], db_path: Path | None = None) -> dict[str, int]:
    """Return row counts for quick health checks."""
    path = initialize_database(db_path)
    counts: dict[str, int] = {}
    with connect(path) as connection:
        for table_name in table_names:
            row = connection.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
            counts[table_name] = int(row["count"])
    return counts

