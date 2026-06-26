# API Documentation

Run locally:

```powershell
uvicorn api.main:app --reload
```

Base URL:

```text
http://127.0.0.1:8000
```

## GET /health

Returns service status, database path, and table counts.

### Example Response

```json
{
  "status": "ok",
  "database": "data/processed/dispatch.db",
  "counts": {
    "nodes": 100,
    "vehicles": 16,
    "shipments": 120
  }
}
```

## POST /optimize

Runs dispatch optimization and persists the latest result.

### Request Body

```json
{
  "optimization_mode": "balanced",
  "max_route_duration_hours": 8,
  "include_priority_only": false,
  "congestion_factor": 1.0,
  "force_fallback": false,
  "regenerate_data": false,
  "shipments": 120,
  "vehicles": 16
}
```

### Response

```json
{
  "plan_id": "PLAN-20260626090000",
  "total_shipments": 120,
  "assigned_shipments": 96,
  "unassigned_shipments": 24,
  "total_cost": 15420.5,
  "sla_risk_count": 12,
  "vehicle_utilization_avg": 71.4,
  "engine": "fallback"
}
```

## GET /dispatch-plan

Returns latest optimization run, dispatch plan rows, route summary rows, and unassigned shipment rows.

## GET /sla-risks

Returns shipments with `High` or `Critical` SLA risk, plus expected late deliveries.

## GET /vehicle-utilization

Returns utilization, distance, cost, and assigned shipment counts by vehicle.
