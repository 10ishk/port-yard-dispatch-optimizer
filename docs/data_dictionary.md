# Data Dictionary

## shipments

- `shipment_id`: unique shipment id
- `waybill_number`: synthetic waybill number
- `customer_id`: synthetic customer id
- `priority`: `Low`, `Medium`, `High`, `Critical`
- `origin_node`: pickup or origin node
- `destination_node`: delivery node
- `destination_lat`, `destination_lon`: destination coordinates
- `weight_kg`: shipment weight
- `volume_cbm`: shipment volume
- `service_type`: `Express`, `Standard`, `Economy`, `Heavy Cargo`
- `earliest_delivery_time`: earliest acceptable delivery time
- `latest_delivery_time`: latest acceptable delivery time
- `promised_delivery_time`: customer promise time used for SLA risk
- `handling_type`: `Normal`, `Fragile`, `Cold Chain`, `Heavy`
- `revenue`: synthetic shipment revenue
- `penalty_if_late`: synthetic SLA penalty
- `status`: shipment status
- `created_at`: synthetic creation timestamp

## vehicles

- `vehicle_id`: unique vehicle id
- `vehicle_type`: `Van`, `3T Truck`, `7T Truck`, `Trailer`
- `capacity_kg`: weight capacity
- `capacity_cbm`: volume capacity
- `cost_per_km`: operating cost per kilometer
- `avg_speed_kmph`: average route speed
- `available_from`, `available_until`: vehicle availability window
- `start_node`: vehicle starting location
- `driver_id`: synthetic driver id
- `active_flag`: active vehicle indicator

## nodes

- `node_id`: unique node id
- `node_name`: synthetic location name
- `node_type`: `Depot`, `Hub`, `Yard`, `Customer`, `Port Gate`, `Warehouse`
- `latitude`, `longitude`: synthetic coordinates
- `region`: UAE/GCC-inspired region
- `operating_start`, `operating_end`: operating window

## dispatch_plan

- `plan_id`: optimization run id
- `vehicle_id`: assigned vehicle
- `stop_sequence`: route stop order
- `shipment_id`: assigned shipment
- `planned_arrival`, `planned_departure`: planned stop timestamps
- `distance_from_previous_km`: segment distance
- `cumulative_distance_km`: cumulative route distance
- `expected_late_flag`: late-delivery indicator
- `route_cost`: stop-level cost including late penalty
- `utilization_kg_pct`, `utilization_cbm_pct`: vehicle utilization after the stop
- `sla_risk_score`, `sla_risk_category`: SLA risk output
- `risk_reason`, `suggested_action`: exception-management fields
