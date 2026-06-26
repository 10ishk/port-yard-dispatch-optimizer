# Setup

## Requirements

- Python 3.12
- Git
- Optional: GitHub CLI for publishing

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Generate Synthetic Data

```powershell
python src/generate_synthetic_data.py --shipments 500 --vehicles 40
```

## Run Optimizer

```powershell
python src/optimize_routes.py --optimization-mode balanced --max-route-duration-hours 8
```

Fallback mode:

```powershell
python src/optimize_routes.py --force-fallback
```

## Run API

```powershell
uvicorn api.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Run Dashboard

```powershell
streamlit run app/streamlit_app.py
```

## Run Tests

```powershell
pytest
```
