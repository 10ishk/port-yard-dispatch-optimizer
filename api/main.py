"""FastAPI service for dispatch optimization and monitoring."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DEFAULT_SHIPMENTS, DEFAULT_VEHICLES, get_database_path  # noqa: E402
from src.database import has_input_data, load_table, table_counts  # noqa: E402
from src.generate_synthetic_data import generate_dataset  # noqa: E402
from src.database import write_base_dataset  # noqa: E402
from src.optimize_routes import optimize_dispatch  # noqa: E402


app = FastAPI(
    title="Port Yard Dispatch Optimizer API",
    description="Optimization endpoints for synthetic port and yard logistics planning.",
    version="0.1.0",
)


class OptimizeRequest(BaseModel):
    optimization_mode: Literal[
        "balanced", "minimize_cost", "minimize_delay", "maximize_utilization"
    ] = "balanced"
    max_route_duration_hours: float = Field(default=8.0, ge=1.0, le=14.0)
    include_priority_only: bool = False
    congestion_factor: float = Field(default=1.0, ge=0.5, le=2.5)
    force_fallback: bool = False
    regenerate_data: bool = False
    shipments: int = Field(default=DEFAULT_SHIPMENTS, ge=1, le=2000)
    vehicles: int = Field(default=DEFAULT_VEHICLES, ge=1, le=250)


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    if frame.empty:
        return []
    cleaned = frame.replace({np.nan: None})
    return cleaned.to_dict(orient="records")


def _ensure_base_data() -> None:
    db_path = get_database_path()
    if not has_input_data(db_path):
        shipments, vehicles, nodes = generate_dataset(DEFAULT_SHIPMENTS, DEFAULT_VEHICLES)
        write_base_dataset(shipments, vehicles, nodes, db_path)


def _ensure_latest_plan() -> None:
    _ensure_base_data()
    if load_table("optimization_runs").empty:
        optimize_dispatch(export_csv=False)


@app.get("/health")
def health() -> dict[str, object]:
    _ensure_base_data()
    counts = table_counts(
        [
            "nodes",
            "vehicles",
            "shipments",
            "dispatch_plan",
            "route_summary",
            "unassigned_shipments",
        ]
    )
    return {
        "status": "ok",
        "database": str(get_database_path()),
        "counts": counts,
    }


@app.post("/optimize")
def optimize(request: OptimizeRequest) -> dict[str, object]:
    result = optimize_dispatch(
        optimization_mode=request.optimization_mode,
        max_route_duration_hours=request.max_route_duration_hours,
        include_priority_only=request.include_priority_only,
        congestion_factor=request.congestion_factor,
        force_fallback=request.force_fallback,
        regenerate_data=request.regenerate_data,
        generated_shipments=request.shipments,
        generated_vehicles=request.vehicles,
        export_csv=True,
    )
    summary = result["run_summary"].iloc[0].to_dict()
    return {
        "plan_id": summary["plan_id"],
        "total_shipments": int(summary["total_shipments"]),
        "assigned_shipments": int(summary["assigned_shipments"]),
        "unassigned_shipments": int(summary["unassigned_shipments"]),
        "total_cost": float(summary["total_cost"]),
        "sla_risk_count": int(summary["sla_risk_count"]),
        "vehicle_utilization_avg": float(summary["vehicle_utilization_avg"]),
        "engine": summary["engine"],
    }


@app.get("/dispatch-plan")
def dispatch_plan() -> dict[str, object]:
    _ensure_latest_plan()
    return {
        "latest_run": _records(load_table("optimization_runs")),
        "dispatch_plan": _records(load_table("dispatch_plan")),
        "route_summary": _records(load_table("route_summary")),
        "unassigned_shipments": _records(load_table("unassigned_shipments")),
    }


@app.get("/sla-risks")
def sla_risks() -> dict[str, object]:
    _ensure_latest_plan()
    dispatch = load_table("dispatch_plan")
    shipments = load_table("shipments")
    if dispatch.empty:
        return {"sla_risks": []}
    risks = dispatch[
        dispatch["sla_risk_category"].isin(["High", "Critical"]) | (dispatch["expected_late_flag"] == 1)
    ].copy()
    if not risks.empty:
        risks = risks.merge(
            shipments[
                [
                    "shipment_id",
                    "waybill_number",
                    "priority",
                    "promised_delivery_time",
                    "latest_delivery_time",
                    "penalty_if_late",
                ]
            ],
            on="shipment_id",
            how="left",
        )
    return {"sla_risks": _records(risks)}


@app.get("/vehicle-utilization")
def vehicle_utilization() -> dict[str, object]:
    _ensure_latest_plan()
    summary = load_table("route_summary")
    return {"vehicle_utilization": _records(summary)}

