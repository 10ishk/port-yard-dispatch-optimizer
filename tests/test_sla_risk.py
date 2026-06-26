from __future__ import annotations

from datetime import datetime

from src.cost_model import calculate_late_minutes, calculate_stop_cost
from src.sla_risk import calculate_sla_risk, risk_category


SHIPMENT = {
    "priority": "Critical",
    "earliest_delivery_time": "2026-01-15T09:00",
    "latest_delivery_time": "2026-01-15T12:00",
    "promised_delivery_time": "2026-01-15T11:30",
    "revenue": 1200.0,
    "penalty_if_late": 450.0,
}


def test_late_shipment_scores_as_high_or_critical():
    risk = calculate_sla_risk(SHIPMENT, "2026-01-15T12:15", route_congestion_factor=1.35)

    assert risk["delay_minutes"] == 45.0
    assert risk["sla_risk_category"] in {"High", "Critical"}
    assert "after promise" in risk["risk_reason"]


def test_on_time_low_priority_shipment_has_lower_risk():
    shipment = dict(SHIPMENT)
    shipment["priority"] = "Low"
    shipment["revenue"] = 100.0

    risk = calculate_sla_risk(shipment, "2026-01-15T10:00", route_congestion_factor=1.0)

    assert risk["delay_minutes"] == 0.0
    assert risk["sla_risk_score"] < 50


def test_cost_model_adds_late_penalty():
    late_minutes = calculate_late_minutes(
        datetime(2026, 1, 15, 12, 10),
        datetime(2026, 1, 15, 11, 30),
    )
    cost = calculate_stop_cost(25.0, 3.0, late_minutes, 200.0)

    assert late_minutes == 40.0
    assert cost > 25.0 * 3.0
    assert risk_category(81) == "Critical"

