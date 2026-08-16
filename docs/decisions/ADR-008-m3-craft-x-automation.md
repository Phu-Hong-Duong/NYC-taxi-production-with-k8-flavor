# ADR-008 — M3 redesigned: craft and automation side by side, equal budgets
- Status: accepted (PO direction)
- Date: 2026-08-12
- Context: PO direction, verbatim: "I want it to make full use of the best
  wisdom from Kaggle competition or other sources on the internet, where the
  professional perform rigid feature engineering and leverage the expertise to
  toy with ML algorithm until they achieve the best result. ... I actually want
  to experience the convenience of AutoML + optuna, and the worflow ML of a
  true professional side by side in this case."
- Options: (a) automation-only M3 (v2.2 shape) · (b) artisan-only "Kaggle mode"
  · (c) both tracks, equal budgets, 2x2 bake-off.
- Choice: (c). Artisan track = community-harvested feature dossier + budgeted
  expert iteration + ablation evidence; automation track = FLAML scout + Optuna
  sniper run on BOTH feature sets; five-contender bake-off isolates
  features-vs-tuning contribution; unchanged promotion gate judges all.
- Honest cost: M3 grows to ~two sessions (split at S2/S3); the artisan budget
  must be enforced or "toying until best" becomes unbounded Kaggle grinding —
  the wall-clock parity rule is the guard.
- Amends: ADR-007 (scout/sniper design carried intact into track S3; nothing
  loosened). Revisit trigger: OSRM routing / weather joins wanted -> M9 stretch
  fork, not silent M3 growth.
