# Port Yard Dispatch Optimizer

Port Yard Dispatch Optimizer is a Python logistics planning prototype for port-linked and yard dispatch operations. It generates synthetic shipment, vehicle, and node data, assigns shipments to vehicles, sequences delivery stops, estimates route cost, and highlights SLA risk.

The project uses fictional UAE/GCC-inspired locations and does not include real company, carrier, customer, or shipment data.

## Business Problem

Dispatch teams often need to balance vehicle capacity, delivery windows, priority shipments, cost control, and operational exceptions under time pressure. Manual planning can leave vehicles underutilized, miss promised delivery times, or hide high-risk shipments until escalation is already needed.

This project models that workflow as a transport planning system for dispatchers, transport managers, and control tower analysts.

## Features

- Synthetic generation for shipments, vehicles, depots, hubs, yards, warehouses, and customer nodes.
- Haversine distance matrix for route distance estimates.
- OR-Tools vehicle routing integration with a deterministic greedy fallback.
- Capacity checks for weight and volume.
- Delivery time windows, vehicle availability windows, and max route duration.
- Priority shipment handling and SLA risk scoring.
- Route cost, late penalty, utilization, and unassigned shipment reporting.
- FastAPI endpoints for optimization and monitoring.
- Streamlit dashboard with overview, planner, map, SLA exceptions, and what-if simulation.
- CSV export for dispatch plans, route summaries, and unassigned shipments.
- SQLite persistence for a portable local setup.

## Tech Stack

- Python 3.12
- Google OR-Tools
- FastAPI
- Streamlit
- SQLite
- pandas, numpy
- Plotly, Folium
- SQLAlchemy, Pydantic
- pytest

## Folder Structure

```text
.
├── api/                  # FastAPI service
├── app/                  # Streamlit dashboard
├── data/                 # Runtime and sample data folders
├── docs/                 # Project documentation
├── outputs/              # Generated dispatch exports
├── sql/                  # SQLite schema and analysis queries
├── src/                  # Data generation and optimization modules
└── tests/                # pytest coverage
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Generate Data

```powershell
python src/generate_synthetic_data.py --shipments 500 --vehicles 40
```

This writes CSV files under `data/raw/`, sample CSVs under `data/sample/`, and SQLite tables to `data/processed/dispatch.db`.

## Run Optimization

```powershell
python src/optimize_routes.py --optimization-mode balanced --max-route-duration-hours 8
```

Use the fallback engine explicitly:

```powershell
python src/optimize_routes.py --force-fallback
```

Generated plan exports are written to `outputs/dispatch_plans/`.

## Run API

```powershell
uvicorn api.main:app --reload
```

Core endpoints:

- `GET /health`
- `POST /optimize`
- `GET /dispatch-plan`
- `GET /sla-risks`
- `GET /vehicle-utilization`

Example optimization request:

```json
{
  "optimization_mode": "balanced",
  "max_route_duration_hours": 8,
  "include_priority_only": false
}
```

## Run Dashboard

```powershell
streamlit run app/streamlit_app.py
```

Dashboard views:

- Dispatch Overview
- Optimization Planner
- Route Map
- SLA Risk and Exceptions
- What-if Simulation

## Database

SQLite is used for local portability. Main tables:

- `shipments`
- `vehicles`
- `nodes`
- `dispatch_plan`
- `route_summary`
- `unassigned_shipments`
- `optimization_runs`

See [docs/database.md](docs/database.md) and [docs/data_dictionary.md](docs/data_dictionary.md).

## Screenshots

Screenshots should be captured from the local Streamlit dashboard after launching the app:

```powershell
streamlit run app/streamlit_app.py
```

Recommended captures:

- Dispatch Overview KPI and charts
- Optimization Planner results table
- Route Map with vehicle paths
- SLA Risk and Exceptions table
- What-if Simulation result

## Testing

```powershell
pytest
```

The tests cover capacity constraints, SLA risk scoring, cost calculations, fallback planning, optimizer output shape, and API smoke checks.

## Future Improvements

- Real traffic simulation
- Driver shift constraints
- Multi-depot routing
- Split deliveries
- Predictive ETA model
- Geofence alerts
- Yard queue simulation
- Customer notification workflow
