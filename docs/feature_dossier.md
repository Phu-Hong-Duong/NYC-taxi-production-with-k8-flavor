# Feature dossier — M3-S1 (harvested live; template seeded 2026-08-12)

Sources to mine at execution (live, not from memory): the 2017 Kaggle NYC
taxi-trip-duration competition (top-solution write-ups and kernels) · strong
MLOps-zoomcamp capstones · current blog write-ups. Adaptation reality: 2019+
TLC files carry PU/DO zone IDs, not lat/lon — coordinate-derived ideas are
adapted via TLC zone-shapefile centroids.

Rules: every candidate carries a leakage-risk note BEFORE implementation;
aggregates are fit on TRAIN months only; the verdict column is filled only by
S2's ablation numbers, never by enthusiasm. Survivor aggregates become the
named Feast candidates at M8.

| # | Candidate | Family | Source (link, date read) | Rationale | Leakage risk | Adaptation note | Ablation verdict |
|---|---|---|---|---|---|---|---|
| 1 | hour / weekday / month decomposition | temporal | | | none | | |
| 2 | US + NYC holiday flag | temporal | | | none | | |
| 3 | rush-hour flags | temporal | | | none | | |
| 4 | zone-centroid haversine distance | spatial | | | none | shapefile centroids | |
| 5 | zone-centroid bearing | spatial | | | none | shapefile centroids | |
| 6 | airport-zone flags (JFK/LGA/EWR) | spatial | | | none | zone-ID lookup | |
| 7 | circuity = odometer / straight-line | trip | | | none | | |
| 8 | zone-pair median duration | aggregate | | | HIGH — train-only fit | | |
| 9 | PU-zone x hour mean speed | aggregate | | | HIGH — train-only fit | | |
| 10 | log1p(duration) target transform | target | | | none | invert before MAE | |
| … | (harvest more live) | | | | | | |
