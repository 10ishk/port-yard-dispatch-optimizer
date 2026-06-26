from __future__ import annotations

from src.optimize_routes import optimize_dispatch


def test_optimizer_returns_expected_frames(sample_dataset):
    shipments, vehicles, nodes = sample_dataset
    result = optimize_dispatch(
        shipments=shipments,
        vehicles=vehicles,
        nodes=nodes,
        persist=False,
        export_csv=False,
        force_fallback=True,
        optimization_mode="balanced",
    )

    assert result["plan_id"].startswith("PLAN-")
    assert set(result) >= {
        "dispatch_plan",
        "route_summary",
        "unassigned_shipments",
        "run_summary",
        "engine",
    }
    assert result["engine"] == "fallback"
    assert result["run_summary"].iloc[0]["assigned_shipments"] == len(result["dispatch_plan"])


def test_each_shipment_is_assigned_at_most_once(sample_dataset):
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

    assert dispatch["shipment_id"].is_unique


def test_priority_only_limits_planned_shipments(sample_dataset):
    shipments, vehicles, nodes = sample_dataset
    high_priority_count = int(shipments["priority"].isin(["High", "Critical"]).sum())
    result = optimize_dispatch(
        shipments=shipments,
        vehicles=vehicles,
        nodes=nodes,
        persist=False,
        export_csv=False,
        force_fallback=True,
        include_priority_only=True,
    )

    run = result["run_summary"].iloc[0]
    assert int(run["total_shipments"]) == high_priority_count

