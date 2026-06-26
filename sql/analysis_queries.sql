-- Latest optimization run.
SELECT *
FROM optimization_runs
ORDER BY created_at DESC
LIMIT 1;

-- SLA risk by category for the latest dispatch plan.
SELECT sla_risk_category, COUNT(*) AS shipment_count
FROM dispatch_plan
WHERE plan_id = (SELECT plan_id FROM optimization_runs ORDER BY created_at DESC LIMIT 1)
GROUP BY sla_risk_category
ORDER BY shipment_count DESC;

-- Vehicle utilization for the latest dispatch plan.
SELECT
    vehicle_id,
    vehicle_type,
    assigned_shipments,
    utilization_kg_pct,
    utilization_cbm_pct,
    total_distance_km,
    total_cost
FROM route_summary
WHERE plan_id = (SELECT plan_id FROM optimization_runs ORDER BY created_at DESC LIMIT 1)
ORDER BY utilization_kg_pct DESC;

