PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS nodes (
    node_id TEXT PRIMARY KEY,
    node_name TEXT NOT NULL,
    node_type TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    region TEXT NOT NULL,
    operating_start TEXT NOT NULL,
    operating_end TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_id TEXT PRIMARY KEY,
    vehicle_type TEXT NOT NULL,
    capacity_kg REAL NOT NULL,
    capacity_cbm REAL NOT NULL,
    cost_per_km REAL NOT NULL,
    avg_speed_kmph REAL NOT NULL,
    available_from TEXT NOT NULL,
    available_until TEXT NOT NULL,
    start_node TEXT NOT NULL,
    driver_id TEXT NOT NULL,
    active_flag INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (start_node) REFERENCES nodes (node_id)
);

CREATE TABLE IF NOT EXISTS shipments (
    shipment_id TEXT PRIMARY KEY,
    waybill_number TEXT NOT NULL UNIQUE,
    customer_id TEXT NOT NULL,
    priority TEXT NOT NULL,
    origin_node TEXT NOT NULL,
    destination_node TEXT NOT NULL,
    destination_lat REAL NOT NULL,
    destination_lon REAL NOT NULL,
    weight_kg REAL NOT NULL,
    volume_cbm REAL NOT NULL,
    service_type TEXT NOT NULL,
    earliest_delivery_time TEXT NOT NULL,
    latest_delivery_time TEXT NOT NULL,
    promised_delivery_time TEXT NOT NULL,
    handling_type TEXT NOT NULL,
    revenue REAL NOT NULL,
    penalty_if_late REAL NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (origin_node) REFERENCES nodes (node_id),
    FOREIGN KEY (destination_node) REFERENCES nodes (node_id)
);

CREATE TABLE IF NOT EXISTS dispatch_plan (
    plan_id TEXT NOT NULL,
    vehicle_id TEXT NOT NULL,
    stop_sequence INTEGER NOT NULL,
    shipment_id TEXT NOT NULL,
    planned_arrival TEXT NOT NULL,
    planned_departure TEXT NOT NULL,
    distance_from_previous_km REAL NOT NULL,
    cumulative_distance_km REAL NOT NULL,
    expected_late_flag INTEGER NOT NULL,
    route_cost REAL NOT NULL,
    utilization_kg_pct REAL NOT NULL,
    utilization_cbm_pct REAL NOT NULL,
    sla_risk_score REAL NOT NULL,
    sla_risk_category TEXT NOT NULL,
    risk_reason TEXT NOT NULL,
    suggested_action TEXT NOT NULL,
    PRIMARY KEY (plan_id, vehicle_id, stop_sequence)
);

CREATE TABLE IF NOT EXISTS route_summary (
    plan_id TEXT NOT NULL,
    vehicle_id TEXT NOT NULL,
    vehicle_type TEXT NOT NULL,
    assigned_shipments INTEGER NOT NULL,
    total_weight_kg REAL NOT NULL,
    total_volume_cbm REAL NOT NULL,
    total_distance_km REAL NOT NULL,
    total_cost REAL NOT NULL,
    utilization_kg_pct REAL NOT NULL,
    utilization_cbm_pct REAL NOT NULL,
    route_start TEXT NOT NULL,
    route_end TEXT NOT NULL,
    sla_risk_count INTEGER NOT NULL,
    PRIMARY KEY (plan_id, vehicle_id)
);

CREATE TABLE IF NOT EXISTS unassigned_shipments (
    plan_id TEXT NOT NULL,
    shipment_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    priority TEXT NOT NULL,
    weight_kg REAL NOT NULL,
    volume_cbm REAL NOT NULL,
    latest_delivery_time TEXT NOT NULL,
    PRIMARY KEY (plan_id, shipment_id)
);

CREATE TABLE IF NOT EXISTS optimization_runs (
    plan_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    optimization_mode TEXT NOT NULL,
    max_route_duration_hours REAL NOT NULL,
    include_priority_only INTEGER NOT NULL,
    total_shipments INTEGER NOT NULL,
    assigned_shipments INTEGER NOT NULL,
    unassigned_shipments INTEGER NOT NULL,
    total_cost REAL NOT NULL,
    sla_risk_count INTEGER NOT NULL,
    vehicle_utilization_avg REAL NOT NULL,
    engine TEXT NOT NULL
);

