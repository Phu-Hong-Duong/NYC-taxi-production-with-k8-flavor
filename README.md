# NYC Taxi — Production Pipeline (Kubernetes flavor)

A production-style data pipeline built on the NYC TLC trip record dataset, deployed on Kubernetes.

## Status

Project scaffolding. Nothing implemented yet — this repository starts the development history.

## Getting started

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

## Repository layout

To be filled in as the project takes shape.

## Notes

- Raw data files (`data/`, `*.parquet`, `*.csv`) are intentionally not tracked — see `.gitignore`.
- Secrets (`.env`, kubeconfigs, service-account keys) are never committed.
