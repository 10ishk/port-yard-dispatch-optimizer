from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app


def test_api_health_and_optimize_endpoints():
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    response = client.post(
        "/optimize",
        json={
            "optimization_mode": "balanced",
            "max_route_duration_hours": 8,
            "include_priority_only": False,
            "force_fallback": True,
            "shipments": 30,
            "vehicles": 8,
            "regenerate_data": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["plan_id"].startswith("PLAN-")
    assert body["total_shipments"] == 30
    assert body["engine"] == "fallback"

    plan = client.get("/dispatch-plan")
    assert plan.status_code == 200
    assert "dispatch_plan" in plan.json()

