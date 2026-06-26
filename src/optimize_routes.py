"""Main optimization entrypoint using OR-Tools with greedy fallback."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DEFAULT_SHIPMENTS, DEFAULT_VEHICLES, get_database_path  # noqa: E402
from src.cost_model import as_datetime  # noqa: E402
from src.database import (  # noqa: E402
    has_input_data,
    load_table,
    write_base_dataset,
    write_optimization_outputs,
)
from src.distance_matrix import haversine_km, travel_minutes  # noqa: E402
from src.export_plan import export_dispatch_outputs  # noqa: E402
from src.fallback_heuristic import (  # noqa: E402
    SERVICE_TIME_MINUTES,
    build_dispatch_outputs,
    new_plan_id,
    run_fallback_optimization,
)
from src.generate_synthetic_data import generate_dataset  # noqa: E402


OPTIMIZATION_MODES = ("balanced", "minimize_cost", "minimize_delay", "maximize_utilization")
PRIORITY_DROP_PENALTY = {"Low": 5000, "Medium": 12000, "High": 32000, "Critical": 80000}


def _ensure_input_data(
    db_path: Path,
    shipments: int = DEFAULT_SHIPMENTS,
    vehicles: int = DEFAULT_VEHICLES,
    regenerate: bool = False,
) -> None:
    if regenerate or not has_input_data(db_path):
        shipment_frame, vehicle_frame, node_frame = generate_dataset(shipments, vehicles)
        write_base_dataset(shipment_frame, vehicle_frame, node_frame, db_path)


def _load_inputs(db_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return load_table("shipments", db_path), load_table("vehicles", db_path), load_table("nodes", db_path)


def _minutes_from_start(value: object, planning_start: datetime) -> int:
    return max(0, int(round((as_datetime(value) - planning_start).total_seconds() / 60.0)))


def _solve_with_ortools(
    shipments: pd.DataFrame,
    vehicles: pd.DataFrame,
    nodes: pd.DataFrame,
    *,
    optimization_mode: str,
    max_route_duration_hours: float,
    include_priority_only: bool,
    congestion_factor: float,
    plan_id: str,
    time_limit_seconds: int = 10,
) -> dict[str, Any] | None:
    try:
        from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    except ImportError:
        return None

    considered_shipments = shipments.copy()
    if include_priority_only:
        considered_shipments = considered_shipments[
            considered_shipments["priority"].isin(["High", "Critical"])
        ].copy()
    active_vehicles = vehicles[vehicles["active_flag"].astype(int) == 1].reset_index(drop=True)
    considered_shipments = considered_shipments.reset_index(drop=True)
    if considered_shipments.empty or active_vehicles.empty:
        return None

    nodes_indexed = nodes.set_index("node_id", drop=False)
    route_nodes: list[dict[str, Any]] = []
    for vehicle_number, vehicle in active_vehicles.iterrows():
        start_node = nodes_indexed.loc[str(vehicle["start_node"])]
        route_nodes.append(
            {
                "kind": "start",
                "vehicle_number": int(vehicle_number),
                "vehicle_id": str(vehicle["vehicle_id"]),
                "node_id": str(vehicle["start_node"]),
                "lat": float(start_node["latitude"]),
                "lon": float(start_node["longitude"]),
                "weight_kg": 0.0,
                "volume_cbm": 0.0,
                "shipment_id": None,
                "priority": "Low",
            }
        )
    for _, shipment in considered_shipments.iterrows():
        route_nodes.append(
            {
                "kind": "shipment",
                "shipment_id": str(shipment["shipment_id"]),
                "node_id": str(shipment["destination_node"]),
                "lat": float(shipment["destination_lat"]),
                "lon": float(shipment["destination_lon"]),
                "weight_kg": float(shipment["weight_kg"]),
                "volume_cbm": float(shipment["volume_cbm"]),
                "priority": str(shipment["priority"]),
                "earliest_delivery_time": shipment["earliest_delivery_time"],
                "latest_delivery_time": shipment["latest_delivery_time"],
                "promised_delivery_time": shipment["promised_delivery_time"],
            }
        )

    vehicle_count = len(active_vehicles)
    starts = list(range(vehicle_count))
    ends = starts
    manager = pywrapcp.RoutingIndexManager(len(route_nodes), vehicle_count, starts, ends)
    routing = pywrapcp.RoutingModel(manager)

    def distance_between_node_indexes(from_node: int, to_node: int) -> float:
        origin = route_nodes[from_node]
        destination = route_nodes[to_node]
        return haversine_km(origin["lat"], origin["lon"], destination["lat"], destination["lon"])

    def distance_callback(from_index: int, to_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(distance_between_node_indexes(from_node, to_node) * 1000)

    distance_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(distance_callback_index)

    def time_callback(from_index: int, to_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        distance_km = distance_between_node_indexes(from_node, to_node)
        service_minutes = SERVICE_TIME_MINUTES if route_nodes[from_node]["kind"] == "shipment" else 0
        return int(round(travel_minutes(distance_km, 52.0, congestion_factor) + service_minutes))

    time_callback_index = routing.RegisterTransitCallback(time_callback)
    max_route_minutes = int(max_route_duration_hours * 60)
    routing.AddDimension(
        time_callback_index,
        180,
        max_route_minutes + 360,
        False,
        "Time",
    )
    time_dimension = routing.GetDimensionOrDie("Time")

    def weight_callback(from_index: int) -> int:
        node = route_nodes[manager.IndexToNode(from_index)]
        return int(round(float(node["weight_kg"]) * 10))

    def volume_callback(from_index: int) -> int:
        node = route_nodes[manager.IndexToNode(from_index)]
        return int(round(float(node["volume_cbm"]) * 100))

    weight_callback_index = routing.RegisterUnaryTransitCallback(weight_callback)
    volume_callback_index = routing.RegisterUnaryTransitCallback(volume_callback)
    routing.AddDimensionWithVehicleCapacity(
        weight_callback_index,
        0,
        [int(round(float(vehicle["capacity_kg"]) * 10)) for _, vehicle in active_vehicles.iterrows()],
        True,
        "Weight",
    )
    routing.AddDimensionWithVehicleCapacity(
        volume_callback_index,
        0,
        [int(round(float(vehicle["capacity_cbm"]) * 100)) for _, vehicle in active_vehicles.iterrows()],
        True,
        "Volume",
    )

    planning_start = min(
        [as_datetime(value) for value in active_vehicles["available_from"]]
        + [as_datetime(value) for value in considered_shipments["earliest_delivery_time"]]
    )
    latest_limit = max(
        [as_datetime(value) for value in active_vehicles["available_until"]]
        + [as_datetime(value) for value in considered_shipments["latest_delivery_time"]]
    )
    horizon_minutes = max(max_route_minutes + 360, _minutes_from_start(latest_limit, planning_start) + 360)
    time_dimension.SetGlobalSpanCostCoefficient(8 if optimization_mode != "maximize_utilization" else 2)

    for vehicle_number, vehicle in active_vehicles.iterrows():
        start_index = routing.Start(int(vehicle_number))
        end_index = routing.End(int(vehicle_number))
        start_minute = _minutes_from_start(vehicle["available_from"], planning_start)
        end_minute = min(
            _minutes_from_start(vehicle["available_until"], planning_start),
            start_minute + max_route_minutes,
        )
        time_dimension.CumulVar(start_index).SetRange(start_minute, start_minute)
        time_dimension.CumulVar(end_index).SetRange(start_minute, max(end_minute, start_minute))

    for node_index, route_node in enumerate(route_nodes[vehicle_count:], start=vehicle_count):
        routing_index = manager.NodeToIndex(node_index)
        earliest = _minutes_from_start(route_node["earliest_delivery_time"], planning_start)
        latest = min(_minutes_from_start(route_node["latest_delivery_time"], planning_start), horizon_minutes)
        if latest >= earliest:
            time_dimension.CumulVar(routing_index).SetRange(earliest, latest)
        promised = _minutes_from_start(route_node["promised_delivery_time"], planning_start)
        soft_penalty = 20 if optimization_mode == "minimize_delay" else 9
        time_dimension.SetCumulVarSoftUpperBound(routing_index, promised, soft_penalty)
        priority = str(route_node["priority"])
        penalty = PRIORITY_DROP_PENALTY.get(priority, 8000)
        if optimization_mode == "maximize_utilization":
            penalty = int(penalty * 1.2)
        routing.AddDisjunction([routing_index], penalty)

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search_parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_parameters.time_limit.FromSeconds(time_limit_seconds)
    solution = routing.SolveWithParameters(search_parameters)
    if solution is None:
        return None

    route_assignments: dict[str, list[str]] = {}
    for vehicle_number, vehicle in active_vehicles.iterrows():
        vehicle_id = str(vehicle["vehicle_id"])
        route_assignments[vehicle_id] = []
        index = routing.Start(int(vehicle_number))
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route_node = route_nodes[node_index]
            if route_node["kind"] == "shipment" and route_node["shipment_id"]:
                route_assignments[vehicle_id].append(str(route_node["shipment_id"]))
            index = solution.Value(routing.NextVar(index))

    assigned_ids = {shipment_id for route in route_assignments.values() for shipment_id in route}
    unassigned_reasons = {
        str(shipment["shipment_id"]): "Not selected by OR-Tools within capacity or time constraints"
        for _, shipment in considered_shipments.iterrows()
        if str(shipment["shipment_id"]) not in assigned_ids
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
        engine="ortools",
        congestion_factor=congestion_factor,
        unassigned_reasons=unassigned_reasons,
    )


def optimize_dispatch(
    *,
    optimization_mode: str = "balanced",
    max_route_duration_hours: float = 8.0,
    include_priority_only: bool = False,
    congestion_factor: float = 1.0,
    db_path: Path | None = None,
    persist: bool = True,
    export_csv: bool = True,
    force_fallback: bool = False,
    regenerate_data: bool = False,
    generated_shipments: int = DEFAULT_SHIPMENTS,
    generated_vehicles: int = DEFAULT_VEHICLES,
    shipments: pd.DataFrame | None = None,
    vehicles: pd.DataFrame | None = None,
    nodes: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Run a dispatch optimization and optionally persist the latest result."""
    if optimization_mode not in OPTIMIZATION_MODES:
        raise ValueError(f"Unsupported optimization_mode: {optimization_mode}")

    path = db_path or get_database_path()
    if shipments is None or vehicles is None or nodes is None:
        _ensure_input_data(path, generated_shipments, generated_vehicles, regenerate_data)
        shipments, vehicles, nodes = _load_inputs(path)

    plan_id = new_plan_id()
    result = None
    if not force_fallback:
        result = _solve_with_ortools(
            shipments,
            vehicles,
            nodes,
            optimization_mode=optimization_mode,
            max_route_duration_hours=max_route_duration_hours,
            include_priority_only=include_priority_only,
            congestion_factor=congestion_factor,
            plan_id=plan_id,
        )
    if result is None:
        result = run_fallback_optimization(
            shipments,
            vehicles,
            nodes,
            optimization_mode=optimization_mode,
            max_route_duration_hours=max_route_duration_hours,
            include_priority_only=include_priority_only,
            congestion_factor=congestion_factor,
            plan_id=plan_id,
        )

    if persist:
        write_optimization_outputs(
            result["dispatch_plan"],
            result["route_summary"],
            result["unassigned_shipments"],
            result["run_summary"],
            path,
        )
    if export_csv:
        export_dispatch_outputs(
            result["plan_id"],
            result["dispatch_plan"],
            result["route_summary"],
            result["unassigned_shipments"],
        )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Optimize a synthetic dispatch plan.")
    parser.add_argument("--optimization-mode", choices=OPTIMIZATION_MODES, default="balanced")
    parser.add_argument("--max-route-duration-hours", type=float, default=8.0)
    parser.add_argument("--include-priority-only", action="store_true")
    parser.add_argument("--congestion-factor", type=float, default=1.0)
    parser.add_argument("--force-fallback", action="store_true")
    parser.add_argument("--regenerate-data", action="store_true")
    parser.add_argument("--shipments", type=int, default=DEFAULT_SHIPMENTS)
    parser.add_argument("--vehicles", type=int, default=DEFAULT_VEHICLES)
    parser.add_argument("--db-path", type=Path, default=get_database_path())
    parser.add_argument("--skip-export", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = optimize_dispatch(
        optimization_mode=args.optimization_mode,
        max_route_duration_hours=args.max_route_duration_hours,
        include_priority_only=args.include_priority_only,
        congestion_factor=args.congestion_factor,
        db_path=args.db_path,
        export_csv=not args.skip_export,
        force_fallback=args.force_fallback,
        regenerate_data=args.regenerate_data,
        generated_shipments=args.shipments,
        generated_vehicles=args.vehicles,
    )
    summary = result["run_summary"].iloc[0].to_dict()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

