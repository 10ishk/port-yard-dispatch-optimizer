# Project Walkthrough

## 1. Generate Data

Create synthetic shipments, vehicles, and location nodes:

```powershell
python src/generate_synthetic_data.py --shipments 500 --vehicles 40
```

## 2. Run Planning

Run a balanced optimization:

```powershell
python src/optimize_routes.py --optimization-mode balanced
```

The optimizer writes latest results to SQLite and CSV exports under `outputs/dispatch_plans/`.

## 3. Inspect API

Start FastAPI:

```powershell
uvicorn api.main:app --reload
```

Open `http://127.0.0.1:8000/docs` and run `/optimize`, `/dispatch-plan`, `/sla-risks`, and `/vehicle-utilization`.

## 4. Use Dashboard

Start Streamlit:

```powershell
streamlit run app/streamlit_app.py
```

Review dispatch KPIs, rerun optimization, inspect routes on the map, and test disruptions in the what-if simulation.

## 5. Validate

Run:

```powershell
pytest
```

The tests confirm capacity constraints, risk scoring, optimizer output shape, and API behavior.
