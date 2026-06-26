"""Route cost and utilization calculations."""

from __future__ import annotations

from datetime import datetime

import pandas as pd


def as_datetime(value: object) -> datetime:
    """Parse pandas, string, or datetime values into a Python datetime."""
    if isinstance(value, datetime):
        return value
    return pd.to_datetime(value).to_pydatetime()


def calculate_late_minutes(planned_arrival: object, promised_delivery_time: object) -> float:
    """Return late minutes beyond the promised delivery time."""
    arrival = as_datetime(planned_arrival)
    promised = as_datetime(promised_delivery_time)
    return max(0.0, (arrival - promised).total_seconds() / 60.0)


def calculate_late_penalty(late_minutes: float, penalty_if_late: float) -> float:
    """Estimate late penalty using fixed SLA penalty plus a light minute charge."""
    if late_minutes <= 0:
        return 0.0
    return round(float(penalty_if_late) + (float(late_minutes) * 1.5), 2)


def calculate_stop_cost(
    distance_km: float,
    cost_per_km: float,
    late_minutes: float = 0.0,
    penalty_if_late: float = 0.0,
) -> float:
    """Return segment transport cost plus any SLA penalty."""
    distance_cost = float(distance_km) * float(cost_per_km)
    return round(distance_cost + calculate_late_penalty(late_minutes, penalty_if_late), 2)


def utilization_percent(used: float, capacity: float) -> float:
    """Return capacity utilization as a bounded percentage."""
    if capacity <= 0:
        return 0.0
    return round(min(100.0, max(0.0, (float(used) / float(capacity)) * 100.0)), 2)

