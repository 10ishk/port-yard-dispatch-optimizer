from __future__ import annotations

import pandas as pd

from src.optimize_routes import optimize_dispatch


def test_fallback_dispatch_respects_vehicle_capacity(sample_dataset):
    shipments, vehicles, nodes = sample_dataset
    result = optimize_dispatch(
        shipments=shipments,
        vehicles=vehicles,
        nodes=nodes,
        persist=False,
        export_csv=False,
        force_fallback=True,
    )

    dispatch = result["dispatch_plan"]
    assert not dispatch.empty

    assigned = dispatch.merge(shipments, on="shipment_id", how="left")
    usage = (
        assigned.groupby("vehicle_id")
        .agg(weight_kg=("weight_kg", "sum"), volume_cbm=("volume_cbm", "sum"))
        .reset_index()
        .merge(vehicles, on="vehicle_id", how="left")
    )

    assert (usage["weight_kg"] <= usage["capacity_kg"] + 0.001).all()
    assert (usage["volume_cbm"] <= usage["capacity_cbm"] + 0.001).all()


def test_route_summary_utilization_is_bounded(sample_dataset):
    shipments, vehicles, nodes = sample_dataset
    result = optimize_dispatch(
        shipments=shipments,
        vehicles=vehicles,
        nodes=nodes,
        persist=False,
        export_csv=False,
        force_fallback=True,
    )
    summary = result["route_summary"]

    assert (summary["utilization_kg_pct"].between(0, 100)).all()
    assert (summary["utilization_cbm_pct"].between(0, 100)).all()
    assert pd.api.types.is_numeric_dtype(summary["total_cost"])

