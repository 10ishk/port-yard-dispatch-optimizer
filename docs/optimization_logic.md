# Optimization Logic

## Problem Type

The planner models a vehicle routing problem with capacity constraints, delivery time windows, vehicle availability, shipment priority, route cost, and SLA risk.

## Objective

The optimizer balances:

- Distance-based transport cost
- Late delivery penalties
- Priority shipment pressure
- Vehicle utilization
- Route duration limits

Supported modes:

- `balanced`
- `minimize_cost`
- `minimize_delay`
- `maximize_utilization`

## OR-Tools Path

When OR-Tools is installed, `src/optimize_routes.py` builds a routing model with:

- one route per active vehicle
- weight and volume capacity dimensions
- delivery time-window constraints
- soft promised-time upper bounds
- disjunction penalties so infeasible shipments can remain unassigned

If the solver is unavailable or cannot produce a solution, the planner falls back automatically.

## Fallback Heuristic

The fallback planner:

1. Sorts shipments by priority, latest delivery time, and penalty.
2. Evaluates active vehicles for remaining capacity and route duration.
3. Scores feasible assignments according to the selected optimization mode.
4. Assigns each shipment to the best feasible vehicle.
5. Calculates planned arrival, departure, utilization, cost, late flag, and SLA risk.
6. Reports unassigned shipments with a reason.

## SLA Risk Model

Risk score uses:

- 40% ETA delay or low delivery buffer
- 20% priority level
- 20% congestion factor
- 10% delivery-window tightness
- 10% customer importance inferred from revenue

Categories:

- `Low`: 0-30
- `Medium`: 31-60
- `High`: 61-80
- `Critical`: 81-100
