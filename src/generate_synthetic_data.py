"""Generate synthetic logistics data for the Port Yard Dispatch Optimizer."""

from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (  # noqa: E402
    DEFAULT_RANDOM_SEED,
    RAW_DATA_DIR,
    SAMPLE_DATA_DIR,
    ensure_project_dirs,
    get_database_path,
)
from src.database import write_base_dataset  # noqa: E402


SIMULATION_START = datetime(2026, 1, 15, 6, 0)

REGION_ANCHORS = {
    "Jebel Ali": (25.0118, 55.0617),
    "Dubai South": (24.9048, 55.1614),
    "Abu Dhabi": (24.4539, 54.3773),
    "Sharjah": (25.3463, 55.4209),
    "Ajman": (25.4052, 55.5136),
    "Al Ain": (24.1302, 55.8023),
    "Ras Al Khaimah": (25.8007, 55.9762),
    "Fujairah": (25.1288, 56.3265),
}

CORE_NODES = [
    ("NODE-001", "Jebel Ali Port Gate", "Port Gate", "Jebel Ali", 25.0118, 55.0617),
    ("NODE-002", "Jebel Ali Logistics Yard", "Yard", "Jebel Ali", 24.9927, 55.0904),
    ("NODE-003", "Dubai South Hub", "Hub", "Dubai South", 24.9048, 55.1614),
    ("NODE-004", "Abu Dhabi Freight Depot", "Depot", "Abu Dhabi", 24.4539, 54.3773),
    ("NODE-005", "Sharjah Cross Dock", "Warehouse", "Sharjah", 25.3463, 55.4209),
    ("NODE-006", "Ajman Distribution Hub", "Hub", "Ajman", 25.4052, 55.5136),
    ("NODE-007", "Al Ain Inland Depot", "Depot", "Al Ain", 24.1302, 55.8023),
    ("NODE-008", "Ras Al Khaimah Yard", "Yard", "Ras Al Khaimah", 25.8007, 55.9762),
    ("NODE-009", "Fujairah Port Warehouse", "Warehouse", "Fujairah", 25.1288, 56.3265),
]

PRIORITY_WEIGHTS = {
    "Low": 0.28,
    "Medium": 0.38,
    "High": 0.24,
    "Critical": 0.10,
}

SERVICE_PROFILES = {
    "Express": {"weight": (5, 450), "volume": (0.05, 2.2), "window_hours": (2, 5)},
    "Standard": {"weight": (10, 900), "volume": (0.08, 4.5), "window_hours": (4, 9)},
    "Economy": {"weight": (20, 1200), "volume": (0.10, 6.0), "window_hours": (6, 12)},
    "Heavy Cargo": {"weight": (600, 3500), "volume": (2.5, 14.0), "window_hours": (5, 10)},
}

VEHICLE_TYPES = {
    "Van": {
        "capacity_kg": 1200,
        "capacity_cbm": 8,
        "cost_per_km": 2.4,
        "avg_speed_kmph": 58,
    },
    "3T Truck": {
        "capacity_kg": 3000,
        "capacity_cbm": 18,
        "cost_per_km": 3.6,
        "avg_speed_kmph": 54,
    },
    "7T Truck": {
        "capacity_kg": 7000,
        "capacity_cbm": 35,
        "cost_per_km": 5.1,
        "avg_speed_kmph": 50,
    },
    "Trailer": {
        "capacity_kg": 18000,
        "capacity_cbm": 76,
        "cost_per_km": 8.4,
        "avg_speed_kmph": 46,
    },
}


def _jitter_coordinate(
    lat: float, lon: float, rng: np.random.Generator, scale: float = 0.055
) -> tuple[float, float]:
    return round(float(lat + rng.normal(0, scale)), 6), round(float(lon + rng.normal(0, scale)), 6)


def generate_nodes(customer_nodes: int = 80, seed: int = DEFAULT_RANDOM_SEED) -> pd.DataFrame:
    """Create core logistics nodes plus synthetic customer delivery points."""
    rng = np.random.default_rng(seed)
    rows = [
        {
            "node_id": node_id,
            "node_name": node_name,
            "node_type": node_type,
            "latitude": latitude,
            "longitude": longitude,
            "region": region,
            "operating_start": "05:00",
            "operating_end": "23:00",
        }
        for node_id, node_name, node_type, region, latitude, longitude in CORE_NODES
    ]

    regions = list(REGION_ANCHORS)
    node_types = ["Customer", "Warehouse"]
    for index in range(customer_nodes):
        region = regions[index % len(regions)]
        lat, lon = _jitter_coordinate(*REGION_ANCHORS[region], rng)
        node_type = node_types[0] if rng.random() > 0.18 else node_types[1]
        rows.append(
            {
                "node_id": f"CUST-{index + 1:03d}",
                "node_name": f"{region} {node_type} {index + 1:03d}",
                "node_type": node_type,
                "latitude": lat,
                "longitude": lon,
                "region": region,
                "operating_start": "07:00",
                "operating_end": "21:00",
            }
        )
    return pd.DataFrame(rows)


def generate_vehicles(count: int, seed: int = DEFAULT_RANDOM_SEED) -> pd.DataFrame:
    """Create a synthetic fleet with capacity, cost, and availability windows."""
    rng = np.random.default_rng(seed + 17)
    start_nodes = ["NODE-001", "NODE-002", "NODE-003", "NODE-004", "NODE-005"]
    type_names = list(VEHICLE_TYPES)
    type_probabilities = [0.36, 0.30, 0.24, 0.10]
    rows = []
    for index in range(count):
        vehicle_type = str(rng.choice(type_names, p=type_probabilities))
        profile = VEHICLE_TYPES[vehicle_type]
        available_from = SIMULATION_START + timedelta(minutes=int(rng.integers(0, 150)))
        available_until = SIMULATION_START + timedelta(hours=int(rng.integers(8, 13)))
        rows.append(
            {
                "vehicle_id": f"VEH-{index + 1:03d}",
                "vehicle_type": vehicle_type,
                "capacity_kg": float(profile["capacity_kg"] * rng.uniform(0.92, 1.08)),
                "capacity_cbm": float(profile["capacity_cbm"] * rng.uniform(0.92, 1.08)),
                "cost_per_km": float(profile["cost_per_km"] * rng.uniform(0.94, 1.10)),
                "avg_speed_kmph": float(profile["avg_speed_kmph"] * rng.uniform(0.90, 1.08)),
                "available_from": available_from.isoformat(timespec="minutes"),
                "available_until": available_until.isoformat(timespec="minutes"),
                "start_node": str(rng.choice(start_nodes)),
                "driver_id": f"DRV-{index + 1:03d}",
                "active_flag": 1 if rng.random() > 0.08 else 0,
            }
        )
    return pd.DataFrame(rows)


def generate_shipments(
    count: int,
    nodes: pd.DataFrame,
    seed: int = DEFAULT_RANDOM_SEED,
) -> pd.DataFrame:
    """Create synthetic shipments with delivery windows and penalties."""
    fake = Faker()
    Faker.seed(seed)
    random.seed(seed)
    rng = np.random.default_rng(seed + 29)
    customer_nodes = nodes[nodes["node_type"].isin(["Customer", "Warehouse"])].reset_index(drop=True)
    origin_nodes = ["NODE-001", "NODE-002", "NODE-003", "NODE-004", "NODE-005", "NODE-009"]
    priority_names = list(PRIORITY_WEIGHTS)
    priority_probabilities = list(PRIORITY_WEIGHTS.values())
    service_names = list(SERVICE_PROFILES)
    service_probabilities = [0.24, 0.38, 0.26, 0.12]
    handling_types = ["Normal", "Fragile", "Cold Chain", "Heavy"]
    rows = []

    for index in range(count):
        destination = customer_nodes.iloc[int(rng.integers(0, len(customer_nodes)))]
        priority = str(rng.choice(priority_names, p=priority_probabilities))
        service_type = str(rng.choice(service_names, p=service_probabilities))
        service_profile = SERVICE_PROFILES[service_type]
        earliest_offset_hours = int(rng.integers(2, 12))
        earliest = SIMULATION_START + timedelta(hours=earliest_offset_hours)
        min_window, max_window = service_profile["window_hours"]
        latest = earliest + timedelta(hours=int(rng.integers(min_window, max_window + 1)))
        promised = latest - timedelta(minutes=int(rng.integers(0, 45)))
        weight_min, weight_max = service_profile["weight"]
        volume_min, volume_max = service_profile["volume"]
        weight = round(float(rng.uniform(weight_min, weight_max)), 2)
        volume = round(float(rng.uniform(volume_min, volume_max)), 2)
        if service_type == "Heavy Cargo":
            handling_type = "Heavy"
        else:
            handling_type = str(rng.choice(handling_types, p=[0.70, 0.16, 0.10, 0.04]))
        revenue = round(float((weight * rng.uniform(0.45, 1.3)) + (volume * rng.uniform(35, 85))), 2)
        penalty_factor = {"Low": 0.16, "Medium": 0.24, "High": 0.36, "Critical": 0.55}[priority]
        rows.append(
            {
                "shipment_id": f"SHP-{index + 1:05d}",
                "waybill_number": f"WB{fake.unique.random_number(digits=9, fix_len=True)}",
                "customer_id": f"CUS-{int(rng.integers(1000, 9999))}",
                "priority": priority,
                "origin_node": str(rng.choice(origin_nodes)),
                "destination_node": str(destination["node_id"]),
                "destination_lat": float(destination["latitude"]),
                "destination_lon": float(destination["longitude"]),
                "weight_kg": weight,
                "volume_cbm": volume,
                "service_type": service_type,
                "earliest_delivery_time": earliest.isoformat(timespec="minutes"),
                "latest_delivery_time": latest.isoformat(timespec="minutes"),
                "promised_delivery_time": promised.isoformat(timespec="minutes"),
                "handling_type": handling_type,
                "revenue": revenue,
                "penalty_if_late": round(max(75.0, revenue * penalty_factor), 2),
                "status": "Pending",
                "created_at": (SIMULATION_START - timedelta(hours=int(rng.integers(2, 48)))).isoformat(
                    timespec="minutes"
                ),
            }
        )
    return pd.DataFrame(rows)


def generate_dataset(
    shipment_count: int,
    vehicle_count: int,
    seed: int = DEFAULT_RANDOM_SEED,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate nodes, vehicles, and shipments sized for a planning run."""
    customer_nodes = max(40, min(max(shipment_count // 3, 60), 160))
    nodes = generate_nodes(customer_nodes=customer_nodes, seed=seed)
    vehicles = generate_vehicles(vehicle_count, seed=seed)
    shipments = generate_shipments(shipment_count, nodes, seed=seed)
    return shipments, vehicles, nodes


def export_dataset(
    shipments: pd.DataFrame,
    vehicles: pd.DataFrame,
    nodes: pd.DataFrame,
    *,
    write_sample: bool = True,
) -> None:
    """Write CSV copies of generated data for inspection and dashboard demos."""
    ensure_project_dirs()
    shipments.to_csv(RAW_DATA_DIR / "shipments.csv", index=False)
    vehicles.to_csv(RAW_DATA_DIR / "vehicles.csv", index=False)
    nodes.to_csv(RAW_DATA_DIR / "nodes.csv", index=False)
    if write_sample:
        shipments.head(50).to_csv(SAMPLE_DATA_DIR / "sample_shipments.csv", index=False)
        vehicles.head(20).to_csv(SAMPLE_DATA_DIR / "sample_vehicles.csv", index=False)
        nodes.head(40).to_csv(SAMPLE_DATA_DIR / "sample_nodes.csv", index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate synthetic dispatch planning data.")
    parser.add_argument("--shipments", type=int, default=120, help="Number of shipments to create.")
    parser.add_argument("--vehicles", type=int, default=16, help="Number of vehicles to create.")
    parser.add_argument("--seed", type=int, default=DEFAULT_RANDOM_SEED, help="Random seed.")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=get_database_path(),
        help="SQLite database path.",
    )
    parser.add_argument(
        "--skip-csv",
        action="store_true",
        help="Skip CSV export and only write SQLite data.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    shipments, vehicles, nodes = generate_dataset(args.shipments, args.vehicles, args.seed)
    write_base_dataset(shipments, vehicles, nodes, args.db_path)
    if not args.skip_csv:
        export_dataset(shipments, vehicles, nodes)
    active_vehicles = int(vehicles["active_flag"].sum())
    print(
        "Generated "
        f"{len(shipments)} shipments, {len(vehicles)} vehicles "
        f"({active_vehicles} active), and {len(nodes)} nodes at {args.db_path}."
    )


if __name__ == "__main__":
    main()

