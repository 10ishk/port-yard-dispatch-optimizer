"""SLA risk scoring for planned shipment arrivals."""

from __future__ import annotations

from datetime import datetime
from typing import Mapping

import pandas as pd

from src.cost_model import as_datetime


PRIORITY_RISK = {
    "Low": 15.0,
    "Medium": 35.0,
    "High": 70.0,
    "Critical": 95.0,
}


def risk_category(score: float) -> str:
    """Map numeric SLA risk score to a category."""
    if score <= 30:
        return "Low"
    if score <= 60:
        return "Medium"
    if score <= 80:
        return "High"
    return "Critical"


def _window_tightness_risk(earliest: datetime, latest: datetime) -> float:
    hours = max((latest - earliest).total_seconds() / 3600.0, 0.1)
    return round(max(0.0, min(100.0, ((10.0 - hours) / 10.0) * 100.0)), 2)


def _delay_risk(planned_arrival: datetime, promised_delivery_time: datetime) -> tuple[float, float]:
    delay_minutes = max(0.0, (planned_arrival - promised_delivery_time).total_seconds() / 60.0)
    if delay_minutes > 0:
        return min(100.0, 45.0 + delay_minutes / 1.5), delay_minutes
    buffer_minutes = (promised_delivery_time - planned_arrival).total_seconds() / 60.0
    if buffer_minutes < 15:
        return 38.0, 0.0
    if buffer_minutes < 45:
        return 24.0, 0.0
    return 8.0, 0.0


def _risk_reason(delay_minutes: float, priority: str, score: float) -> str:
    if delay_minutes > 0:
        return f"Planned arrival is {round(delay_minutes)} minutes after promise."
    if priority in {"High", "Critical"} and score >= 60:
        return "Priority shipment has limited delivery buffer."
    if score >= 60:
        return "Tight delivery window and route conditions increase risk."
    return "Planned arrival has acceptable SLA buffer."


def _suggested_action(delay_minutes: float, priority: str, category: str) -> str:
    if delay_minutes > 0 and priority in {"High", "Critical"}:
        return "Reassign to express vehicle"
    if delay_minutes > 0:
        return "Move to earlier route"
    if category == "Critical":
        return "Escalate to dispatcher"
    if category == "High":
        return "Reassign to closer hub"
    if category == "Medium":
        return "Monitor route progress"
    return "No immediate action"


def calculate_sla_risk(
    shipment: Mapping[str, object] | pd.Series,
    planned_arrival: object,
    *,
    route_congestion_factor: float = 1.0,
    customer_importance: float | None = None,
) -> dict[str, object]:
    """Calculate SLA risk score, category, reason, and suggested action."""
    row = shipment.to_dict() if isinstance(shipment, pd.Series) else dict(shipment)
    arrival = as_datetime(planned_arrival)
    promised = as_datetime(row["promised_delivery_time"])
    earliest = as_datetime(row["earliest_delivery_time"])
    latest = as_datetime(row["latest_delivery_time"])
    delay_score, delay_minutes = _delay_risk(arrival, promised)
    priority = str(row["priority"])
    priority_score = PRIORITY_RISK.get(priority, 35.0)
    congestion_score = max(5.0, min(100.0, 20.0 + ((route_congestion_factor - 1.0) * 120.0)))
    window_score = _window_tightness_risk(earliest, latest)
    revenue = float(row.get("revenue", 0.0))
    importance_score = customer_importance
    if importance_score is None:
        importance_score = max(5.0, min(100.0, revenue / 18.0))

    score = round(
        (delay_score * 0.40)
        + (priority_score * 0.20)
        + (congestion_score * 0.20)
        + (window_score * 0.10)
        + (importance_score * 0.10),
        2,
    )
    category = risk_category(score)
    return {
        "sla_risk_score": score,
        "sla_risk_category": category,
        "delay_minutes": round(delay_minutes, 2),
        "risk_reason": _risk_reason(delay_minutes, priority, score),
        "suggested_action": _suggested_action(delay_minutes, priority, category),
    }

