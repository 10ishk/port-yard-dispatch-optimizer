# Architecture

## Overview

The project is organized as a small logistics planning system with shared Python modules powering the CLI, API, and dashboard.

```text
Synthetic data generator -> SQLite -> Optimization engine -> SQLite outputs
                                      -> FastAPI endpoints
                                      -> Streamlit dashboard
                                      -> CSV exports
```

## Main Modules

- `src/generate_synthetic_data.py` creates synthetic shipments, vehicles, and logistics nodes.
- `src/distance_matrix.py` calculates Haversine distances and travel-time estimates.
- `src/optimize_routes.py` runs OR-Tools when installed and falls back to the greedy planner.
- `src/fallback_heuristic.py` assigns and sequences shipments when OR-Tools is unavailable or no solver result is found.
- `src/sla_risk.py` scores shipment risk from ETA buffer, priority, congestion, delivery-window tightness, and revenue importance.
- `src/cost_model.py` calculates segment cost, late penalties, and utilization.
- `api/main.py` exposes optimization and monitoring endpoints.
- `app/streamlit_app.py` provides the operations dashboard.

## Data Flow

1. Generate synthetic operational data.
2. Store base inputs in SQLite.
3. Run optimization with selected planning settings.
4. Persist latest dispatch plan, route summary, unassigned shipments, and run summary.
5. Read the latest plan through API endpoints or the Streamlit dashboard.

## Design Decisions

- SQLite keeps the project easy to run locally.
- OR-Tools is optional at runtime because the fallback planner provides deterministic coverage.
- Generated runtime files are ignored, while sample CSVs are committed as lightweight examples.
- Public documentation presents the project as a logistics planning prototype.
