"""Greedy fallback routing planner for dispatch optimization."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from src.cost_model import (
    as_datetime,
    calculate_late_minutes,
    calculate_stop_cost,
    utilization_percent,
)
from src.distance_matrix import build_node_lookup, distance_between_nodes, travel_minutes
from src.sla_risk import calculate_sla_risk


SERVICE_TIME_MINUTES = 12
HIGH_PRIORITY = {"High", "Critical"}
PRIORITY_RANK = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}

DISPATCH_COLUMNS = [
    "plan_id",
    "vehicle_id",
    "stop_sequence",
    "shipment_id",
    "planned_arrival",
    "planned_departure",
    "distance_from_previous_km",
    "cumulative_distance_km",
    "expected_late_flag",
    "route_cost",
    "utilization_kg_pct",
    "utilization_cbm_pct",
    "sla_risk_score",
    "sla_risk_category",
    "risk_reason",
    "suggested_action",
]

SUMMARY_COLUMNS = [
    "plan_id",
    "vehicle_id",
    "vehicle_type",
    "assigned_shipments",
    "total_weight_kg",
    "total_volume_cbm",
    "total_distance_km",
    "total_cost",
    "utilization_kg_pct",
    "utilization_cbm_pct",
    "route_start",
    "route_end",
    "sla_risk_count",
]

UNASSIGNED_COLUMNS = [
    "plan_id",
    "shipment_id",
    "reason",
    "priority",
    "weight_kg",
    "volume_cbm",
    "latest_delivery_time",
]

RUN_COLUMNS = [
    "plan_id",
    "created_at",
    "optimization_mode",
    "max_route_duration_hours",
    "include_priority_only",
    "total_shipments",
    "assigned_shipments",
    "unassigned_shipments",
    "total_cost",
    "sla_risk_count",
    "vehicle_utilization_avg",
    "engine",
]


def new_plan_id() -> str:
    """Return a readable unique plan id."""
    return f"PLAN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"


def _empty_outputs(plan_id: str, total_shipments: int, mode: str, max_hours: float, engine: str) -> dict[str, Any]:
    run_summary = pd.DataFrame(
        [
            {
                "plan_id": plan_id,
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "optimization_mode": mode,
                "max_route_duration_hours": float(max_hours),
                "include_priority_only": 0,
                "total_shipments": int(total_shipments),
                "assigned_shipments": 0,
                "unassigned_shipments": int(total_shipments),
                "total_cost": 0.0,
                "sla_risk_count": 0,
                "vehicle_utilization_avg": 0.0,
                "engine": engine,
            }
        ],
        columns=RUN_COLUMNS,
    )
    return {
        "plan_id": plan_id,
        "dispatch_plan": pd.DataFrame(columns=DISPATCH_COLUMNS),
        "route_summary": pd.DataFrame(columns=SUMMARY_COLUMNS),
        "unassigned_shipments": pd.DataFrame(columns=UNASSIGNED_COLUMNS),
        "run_summary": run_summary,
        "engine": engine,
    }


def _filter_shipments(shipments: pd.DataFrame, include_priority_only: bool) -> pd.DataFrame:
    filtered = shipments.copy()
    if include_priority_only:
        filtered = filtered[filtered["priority"].isin(HIGH_PRIORITY)].copy()
    filtered["_priority_rank"] = filtered["priority"].map(PRIORITY_RANK).fillna(1)
    filtered["_latest_sort"] = pd.to_datetime(filtered["latest_delivery_time"])
    return filtered.sort_values(
        ["_priority_rank", "_latest_sort", "penalty_if_late"],
        ascending=[False, True, False],
    ).drop(columns=["_priority_rank", "_latest_sort"])


def _candidate_score(
    *,
    optimization_mode: str,
    distance_km: float,
    cost_per_km: float,
    late_minutes: float,
    penalty_if_late: float,
    utilization_after: float,
    priority: str,
) -> float:
    priority_pressure = {"Low": 0.0, "Medium": -25.0, "High": -85.0, "Critical": -180.0}.get(
        priority, 0.0
    )
    base_cost = distance_km * cost_per_km
    if optimization_mode == "minimize_cost":
        return base_cost + priority_pressure
    if optimization_mode == "minimize_delay":
        return (late_minutes * 20.0) + distance_km + priority_pressure
    if optimization_mode == "maximize_utilization":
        return (base_cost * 0.20) - (utilization_after * 1.5) + priority_pressure
    return base_cost + (late_minutes * 9.0) + calculate_stop_cost(0, 0, late_minutes, penalty_if_late) + priority_pressure


def _evaluate_vehicle_candidate(
    state: dict[str, Any],
    shipment: pd.Series,
    node_lookup: dict[str, dict[str, object]],
    optimization_mode: str,
    max_route_duration_hours: float,
    congestion_factor: float,
) -> dict[str, Any] | None:
    vehicle = state["vehicle"]
    new_weight = state["weight_kg"] + float(shipment["weight_kg"])
    new_volume = state["volume_cbm"] + float(shipment["volume_cbm"])
    if new_weight > float(vehicle["capacity_kg"]) or new_volume > float(vehicle["capacity_cbm"]):
        return None

    distance_km = distance_between_nodes(
        str(state["current_node"]),
        str(shipment["destination_node"]),
        node_lookup,
    )
    arrival = state["current_time"] + timedelta(
        minutes=travel_minutes(distance_km, float(vehicle["avg_speed_kmph"]), congestion_factor)
    )
    earliest = as_datetime(shipment["earliest_delivery_time"])
    if arrival < earliest:
        arrival = earliest
    departure = arrival + timedelta(minutes=SERVICE_TIME_MINUTES)
    available_until = as_datetime(vehicle["available_until"])
    route_duration_hours = (departure - state["route_start"]).total_seconds() / 3600.0
    if departure > available_until or route_duration_hours > max_route_duration_hours:
        return None

    late_minutes = calculate_late_minutes(arrival, shipment["promised_delivery_time"])
    utilization_after = max(
        utilization_percent(new_weight, float(vehicle["capacity_kg"])),
        utilization_percent(new_volume, float(vehicle["capacity_cbm"])),
    )
    score = _candidate_score(
        optimization_mode=optimization_mode,
        distance_km=distance_km,
        cost_per_km=float(vehicle["cost_per_km"]),
        late_minutes=late_minutes,
        penalty_if_late=float(shipment["penalty_if_late"]),
        utilization_after=utilization_after,
        priority=str(shipment["priority"]),
    )
    return {
        "score": score,
        "arrival": arrival,
        "departure": departure,
        "distance_km": distance_km,
        "new_weight": new_weight,
        "new_volume": new_volume,
        "route_duration_hours": route_duration_hours,
    }


def _unassigned_reason(
    shipment: pd.Series,
    vehicles: pd.DataFrame,
    max_route_duration_hours: float,
) -> str:
    active = vehicles[vehicles["active_flag"].astype(int) == 1]
    if active.empty:
        return "No active vehicles available"
    if (
        active["capacity_kg"].max() < float(shipment["weight_kg"])
        or active["capacity_cbm"].max() < float(shipment["volume_cbm"])
    ):
        return "Shipment exceeds available vehicle capacity"
    return f"Capacity, availability, or {max_route_duration_hours:g}h route limit prevented assignment"


def build_dispatch_outputs(
    route_assignments: dict[str, list[str]],
    shipments: pd.DataFrame,
    vehicles: pd.DataFrame,
    nodes: pd.DataFrame,
    *,
    plan_id: str,
    optimization_mode: str,
    max_route_duration_hours: float,
    include_priority_only: bool,
    engine: str,
    congestion_factor: float = 1.0,
    unassigned_reasons: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build dispatch, route, unassigned, and run summary frames from route assignments."""
    node_lookup = build_node_lookup(nodes)
    shipments_indexed = shipments.set_index("shipment_id", drop=False)
    vehicles_indexed = vehicles.set_index("vehicle_id", drop=False)
    considered_shipments = _filter_shipments(shipments, include_priority_only)
    considered_ids = set(considered_shipments["shipment_id"].astype(str))
    assigned_ids = {
        shipment_id
        for route in route_assignments.values()
        for shipment_id in route
        if shipment_id in considered_ids
    }
    unassigned_reasons = unassigned_reasons or {}

    dispatch_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for _, vehicle in vehicles[vehicles["active_flag"].astype(int) == 1].iterrows():
        vehicle_id = str(vehicle["vehicle_id"])
        route = [shipment_id for shipment_id in route_assignments.get(vehicle_id, []) if shipment_id in considered_ids]
        current_node = str(vehicle["start_node"])
        current_time = as_datetime(vehicle["available_from"])
        route_start = current_time
        cumulative_distance = 0.0
        total_cost = 0.0
        total_weight = 0.0
        total_volume = 0.0
        route_risk_count = 0

        for sequence, shipment_id in enumerate(route, start=1):
            shipment = shipments_indexed.loc[shipment_id]
            distance_km = distance_between_nodes(current_node, str(shipment["destination_node"]), node_lookup)
            arrival = current_time + timedelta(
                minutes=travel_minutes(distance_km, float(vehicle["avg_speed_kmph"]), congestion_factor)
            )
            earliest = as_datetime(shipment["earliest_delivery_time"])
            if arrival < earliest:
                arrival = earliest
            departure = arrival + timedelta(minutes=SERVICE_TIME_MINUTES)
            late_minutes = calculate_late_minutes(arrival, shipment["promised_delivery_time"])
            stop_cost = calculate_stop_cost(
                distance_km,
                float(vehicle["cost_per_km"]),
                late_minutes,
                float(shipment["penalty_if_late"]),
            )
            risk = calculate_sla_risk(
                shipment,
                arrival,
                route_congestion_factor=congestion_factor,
            )
            cumulative_distance += distance_km
            total_cost += stop_cost
            total_weight += float(shipment["weight_kg"])
            total_volume += float(shipment["volume_cbm"])
            route_risk_count += 1 if risk["sla_risk_category"] in {"High", "Critical"} else 0
            utilization_kg = utilization_percent(total_weight, float(vehicle["capacity_kg"]))
            utilization_cbm = utilization_percent(total_volume, float(vehicle["capacity_cbm"]))
            dispatch_rows.append(
                {
                    "plan_id": plan_id,
                    "vehicle_id": vehicle_id,
                    "stop_sequence": sequence,
                    "shipment_id": shipment_id,
                    "planned_arrival": arrival.isoformat(timespec="minutes"),
                    "planned_departure": departure.isoformat(timespec="minutes"),
                    "distance_from_previous_km": round(distance_km, 3),
                    "cumulative_distance_km": round(cumulative_distance, 3),
                    "expected_late_flag": 1 if late_minutes > 0 else 0,
                    "route_cost": round(stop_cost, 2),
                    "utilization_kg_pct": utilization_kg,
                    "utilization_cbm_pct": utilization_cbm,
                    "sla_risk_score": risk["sla_risk_score"],
                    "sla_risk_category": risk["sla_risk_category"],
                    "risk_reason": risk["risk_reason"],
                    "suggested_action": risk["suggested_action"],
                }
            )
            current_node = str(shipment["destination_node"])
            current_time = departure

        final_utilization_kg = utilization_percent(total_weight, float(vehicle["capacity_kg"]))
        final_utilization_cbm = utilization_percent(total_volume, float(vehicle["capacity_cbm"]))
        summary_rows.append(
            {
                "plan_id": plan_id,
                "vehicle_id": vehicle_id,
                "vehicle_type": str(vehicle["vehicle_type"]),
                "assigned_shipments": len(route),
                "total_weight_kg": round(total_weight, 2),
                "total_volume_cbm": round(total_volume, 2),
                "total_distance_km": round(cumulative_distance, 3),
                "total_cost": round(total_cost, 2),
                "utilization_kg_pct": final_utilization_kg,
                "utilization_cbm_pct": final_utilization_cbm,
                "route_start": route_start.isoformat(timespec="minutes"),
                "route_end": current_time.isoformat(timespec="minutes"),
                "sla_risk_count": route_risk_count,
            }
        )

    unassigned_rows = []
    for shipment_id in sorted(considered_ids - assigned_ids):
        shipment = shipments_indexed.loc[shipment_id]
        unassigned_rows.append(
            {
                "plan_id": plan_id,
                "shipment_id": shipment_id,
                "reason": unassigned_reasons.get(shipment_id, "Not selected within capacity or time constraints"),
                "priority": str(shipment["priority"]),
                "weight_kg": float(shipment["weight_kg"]),
                "volume_cbm": float(shipment["volume_cbm"]),
                "latest_delivery_time": str(shipment["latest_delivery_time"]),
            }
        )

    dispatch_plan = pd.DataFrame(dispatch_rows, columns=DISPATCH_COLUMNS)
    route_summary = pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS)
    unassigned = pd.DataFrame(unassigned_rows, columns=UNASSIGNED_COLUMNS)
    assigned_count = len(assigned_ids)
    total_cost = float(route_summary["total_cost"].sum()) if not route_summary.empty else 0.0
    avg_utilization = (
        float(route_summary[["utilization_kg_pct", "utilization_cbm_pct"]].max(axis=1).mean())
        if not route_summary.empty
        else 0.0
    )
    sla_risk_count = (
        int(dispatch_plan["sla_risk_category"].isin(["High", "Critical"]).sum())
        if not dispatch_plan.empty
        else 0
    )
    run_summary = pd.DataFrame(
        [
            {
                "plan_id": plan_id,
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "optimization_mode": optimization_mode,
                "max_route_duration_hours": float(max_route_duration_hours),
                "include_priority_only": 1 if include_priority_only else 0,
                "total_shipments": len(considered_ids),
                "assigned_shipments": assigned_count,
                "unassigned_shipments": len(unassigned),
                "total_cost": round(total_cost, 2),
                "sla_risk_count": sla_risk_count,
                "vehicle_utilization_avg": round(avg_utilization, 2),
                "engine": engine,
            }
        ],
        columns=RUN_COLUMNS,
    )
    return {
        "plan_id": plan_id,
        "dispatch_plan": dispatch_plan,
        "route_summary": route_summary,
        "unassigned_shipments": unassigned,
        "run_summary": run_summary,
        "engine": engine,
    }


def run_fallback_optimization(
    shipments: pd.DataFrame,
    vehicles: pd.DataFrame,
    nodes: pd.DataFrame,
    *,
    optimization_mode: str = "balanced",
    max_route_duration_hours: float = 8.0,
    include_priority_only: bool = False,
    congestion_factor: float = 1.0,
    plan_id: str | None = None,
) -> dict[str, Any]:
    """Assign shipments to vehicles with a deterministic greedy heuristic."""
    plan_id = plan_id or new_plan_id()
    considered_shipments = _filter_shipments(shipments, include_priority_only)
    active_vehicles = vehicles[vehicles["active_flag"].astype(int) == 1].copy()
    if considered_shipments.empty or active_vehicles.empty:
        result = _empty_outputs(
            plan_id,
            len(considered_shipments),
            optimization_mode,
            max_route_duration_hours,
            "fallback",
        )
        if not considered_shipments.empty:
            result["unassigned_shipments"] = pd.DataFrame(
                [
                    {
                        "plan_id": plan_id,
                        "shipment_id": str(row["shipment_id"]),
                        "reason": "No active vehicles available",
                        "priority": str(row["priority"]),
                        "weight_kg": float(row["weight_kg"]),
                        "volume_cbm": float(row["volume_cbm"]),
                        "latest_delivery_time": str(row["latest_delivery_time"]),
                    }
                    for _, row in considered_shipments.iterrows()
                ],
                columns=UNASSIGNED_COLUMNS,
            )
        return result

    node_lookup = build_node_lookup(nodes)
    states: dict[str, dict[str, Any]] = {}
    for _, vehicle in active_vehicles.iterrows():
        vehicle_dict = vehicle.to_dict()
        vehicle_id = str(vehicle_dict["vehicle_id"])
        start_time = as_datetime(vehicle_dict["available_from"])
        states[vehicle_id] = {
            "vehicle": vehicle_dict,
            "assigned": [],
            "weight_kg": 0.0,
            "volume_cbm": 0.0,
            "current_node": str(vehicle_dict["start_node"]),
            "current_time": start_time,
            "route_start": start_time,
        }

    unassigned_reasons: dict[str, str] = {}
    for _, shipment in considered_shipments.iterrows():
        best_vehicle_id: str | None = None
        best_candidate: dict[str, Any] | None = None
        for vehicle_id, state in states.items():
            candidate = _evaluate_vehicle_candidate(
                state,
                shipment,
                node_lookup,
                optimization_mode,
                max_route_duration_hours,
                congestion_factor,
            )
            if candidate is None:
                continue
            if best_candidate is None or candidate["score"] < best_candidate["score"]:
                best_candidate = candidate
                best_vehicle_id = vehicle_id

        shipment_id = str(shipment["shipment_id"])
        if best_vehicle_id is None or best_candidate is None:
            unassigned_reasons[shipment_id] = _unassigned_reason(
                shipment,
                vehicles,
                max_route_duration_hours,
            )
            continue

        selected_state = states[best_vehicle_id]
        selected_state["assigned"].append(shipment_id)
        selected_state["weight_kg"] = best_candidate["new_weight"]
        selected_state["volume_cbm"] = best_candidate["new_volume"]
        selected_state["current_node"] = str(shipment["destination_node"])
        selected_state["current_time"] = best_candidate["departure"]

    route_assignments = {
        vehicle_id: [str(shipment_id) for shipment_id in state["assigned"]]
        for vehicle_id, state in states.items()
    }
    return build_dispatch_outputs(
        route_assignments,
        shipments,
        vehicles,
        nodes,
        plan_id=plan_id,
        optimization_mode=optimization_mode,
        max_route_duration_hours=max_route_duration_hours,
        include_priority_only=include_priority_only,
        engine="fallback",
        congestion_factor=congestion_factor,
        unassigned_reasons=unassigned_reasons,
    )

