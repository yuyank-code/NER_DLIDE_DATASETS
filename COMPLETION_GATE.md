# NER-SLIDE V6 — completion gate

This repository must not be treated as complete because the downloader or model code exists.

The project is complete only when the following evidence exists in versioned manifests/artifacts:

1. Required real source datasets were actually acquired or a documented, reproducible source-level blocker exists.
2. Every acquired artifact has provenance, retrieval time, observation/release metadata where available, size and SHA-256.
3. Geometry, CRS, spatial coverage, temporal coverage, schema and missingness checks pass.
4. Landslide labels distinguish confirmed positives, usable negatives and unknown observations. Unknown is never silently converted to 0.
5. Predictors are restricted to information available at or before prediction time. Post-event imagery/measurements cannot enter predictors.
6. A leakage-safe spatiotemporal dataset is materialized.
7. Train/calibration/test partitions are fixed before model comparison.
8. The frozen V5 baseline is reproduced on the V6 evaluation dataset where the feature contract permits comparison.
9. Candidate tabular, temporal, spatial and fusion models are evaluated under the same fixed test protocol.
10. PR-AUC, ROC-AUC, precision, recall, F1, Brier/log loss and calibration are reported where applicable.
11. Temporal holdout and geographic/generalization evaluation are performed.
12. Extreme-rainfall and missing/stale-input stress tests are performed.
13. Ablations prove which data families actually improve the model.
14. Calibration is fitted only on the calibration partition.
15. Uncertainty is evaluated rather than merely exposed as an API field.
16. Explainability is computed from the selected model and verified against the feature contract.
17. Operational thresholds are selected against the intended warning/response objective, not an arbitrary probability cutoff.
18. The final model, preprocessing, feature schema, configuration, dependency lock and evaluation report are versioned together.
19. A complete provenance manifest allows the final dataset/model result to be reproduced.

## Non-negotiable

No synthetic records, synthetic terrain, invented labels, fabricated performance numbers, or placeholder model results may be used to satisfy this gate.

If an external service requires credentials or an execution environment not available to the assistant, that limitation must be recorded explicitly. The system must not claim that the corresponding data were collected until an actual acquisition artifact exists.
