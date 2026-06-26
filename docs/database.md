# Database Documentation

SQLite database path:

```text
data/processed/dispatch.db
```

The schema is defined in `sql/schema.sql`.

## Core Tables

### nodes

Stores depots, hubs, yards, warehouses, port gates, and synthetic customer nodes.

Primary key: `node_id`

### vehicles

Stores vehicle capacity, cost, speed, availability, start node, driver id, and active status.

Primary key: `vehicle_id`

### shipments

Stores synthetic shipment demand, destination coordinates, service profile, delivery windows, revenue, late penalty, and status.

Primary key: `shipment_id`

### dispatch_plan

Stores stop-level route output for the latest plan, including planned arrival, planned departure, distance, cost, utilization, and SLA risk.

Primary key: `plan_id`, `vehicle_id`, `stop_sequence`

### route_summary

Stores vehicle-level route totals for the latest plan.

Primary key: `plan_id`, `vehicle_id`

### unassigned_shipments

Stores shipments not assigned by the optimizer and the reason each shipment was left out.

Primary key: `plan_id`, `shipment_id`

### optimization_runs

Stores the latest run-level KPIs, selected planning mode, and engine used.

Primary key: `plan_id`

## Runtime Behavior

Base input tables are replaced when data is regenerated. Output tables are replaced on each optimization run so the API and dashboard always read the latest plan.
