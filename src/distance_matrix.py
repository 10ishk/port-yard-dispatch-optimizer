"""Distance and travel-time utilities for logistics nodes."""

from __future__ import annotations

import math
from typing import Mapping

import pandas as pd


EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance between two coordinates in kilometers."""
    lat1_rad = math.radians(float(lat1))
    lat2_rad = math.radians(float(lat2))
    delta_lat = math.radians(float(lat2) - float(lat1))
    delta_lon = math.radians(float(lon2) - float(lon1))
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    return round(EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 3)


def build_node_lookup(nodes: pd.DataFrame) -> dict[str, dict[str, object]]:
    """Return node rows keyed by node id."""
    return nodes.set_index("node_id").to_dict(orient="index")


def get_node_coordinates(
    node_id: str,
    node_lookup: Mapping[str, Mapping[str, object]],
) -> tuple[float, float]:
    """Return latitude and longitude for a node id."""
    node = node_lookup[node_id]
    return float(node["latitude"]), float(node["longitude"])


def distance_between_nodes(
    origin_node: str,
    destination_node: str,
    node_lookup: Mapping[str, Mapping[str, object]],
) -> float:
    """Return Haversine distance between two logistics nodes."""
    origin_lat, origin_lon = get_node_coordinates(origin_node, node_lookup)
    dest_lat, dest_lon = get_node_coordinates(destination_node, node_lookup)
    return haversine_km(origin_lat, origin_lon, dest_lat, dest_lon)


def travel_minutes(
    distance_km: float,
    avg_speed_kmph: float,
    congestion_factor: float = 1.0,
) -> float:
    """Estimate travel minutes from distance, average speed, and congestion."""
    safe_speed = max(float(avg_speed_kmph), 1.0)
    return (float(distance_km) / safe_speed) * 60.0 * max(float(congestion_factor), 0.1)


def build_distance_matrix(nodes: pd.DataFrame, node_ids: list[str] | None = None) -> pd.DataFrame:
    """Build a square node-to-node distance matrix."""
    lookup = build_node_lookup(nodes)
    selected_ids = node_ids or list(nodes["node_id"])
    matrix = []
    for origin in selected_ids:
        row = []
        for destination in selected_ids:
            row.append(distance_between_nodes(origin, destination, lookup))
        matrix.append(row)
    return pd.DataFrame(matrix, index=selected_ids, columns=selected_ids)

