"""Export optimizer outputs to CSV files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import DISPATCH_OUTPUT_DIR, ensure_project_dirs


def export_dispatch_outputs(
    plan_id: str,
    dispatch_plan: pd.DataFrame,
    route_summary: pd.DataFrame,
    unassigned_shipments: pd.DataFrame,
    output_dir: Path | None = None,
) -> dict[str, Path]:
    """Write optimizer outputs to CSV and return created paths."""
    ensure_project_dirs()
    target_dir = output_dir or DISPATCH_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "dispatch_plan": target_dir / f"{plan_id}_dispatch_plan.csv",
        "route_summary": target_dir / f"{plan_id}_route_summary.csv",
        "unassigned_shipments": target_dir / f"{plan_id}_unassigned_shipments.csv",
    }
    dispatch_plan.to_csv(paths["dispatch_plan"], index=False)
    route_summary.to_csv(paths["route_summary"], index=False)
    unassigned_shipments.to_csv(paths["unassigned_shipments"], index=False)
    return paths

