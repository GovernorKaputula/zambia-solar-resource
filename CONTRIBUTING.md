# Contributing

Contributions should improve the evidence, reproducibility, or accessibility of the study. Run the documented pipeline and checks before proposing a change. Keep source-data changes separate from model changes so their effects can be evaluated independently.

## Useful next investigations

These are planned research directions, not completed features.

1. **Local measurement validation.** Add a permissioned irradiance or inverter-output series with units, device metadata, time zone, missingness, and reuse permission documented. Evaluate source-to-sensor bias by season before claiming improved local accuracy.
2. **Publication-vintage testing.** Build a dated availability archive and check the eight-day delay assumption. Do not represent a current download of historical data as a historical release snapshot.
3. **Seasonal interval calibration.** Compare pooled and seasonal calibration using a newly reserved evaluation period. The 2024–2025 results are already known; do not reuse that period as an untouched test.
4. **Accessible exploration.** Preserve keyboard operation, visible focus, readable chart data tables, and the distinction between interannual variability and forecast intervals.

## Reporting a problem

Include the command, Python version, expected behavior, actual behavior, and the smallest relevant output. Avoid credentials, personal records, and unrelated environment details. For a disputed result, identify its source file and the calculation that does not reconcile.

## Review criteria

- Public claims trace to stored outputs and cited sources.
- Future information cannot alter earlier features.
- Evaluation dates and reasons for changes are recorded.
- Unsuccessful comparisons are retained when they informed a decision.
- Changes to assumptions are visible in the study and application.
