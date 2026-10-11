"""Independent SQLite aggregation of exported holdout predictions."""
import json
from pathlib import Path
import sqlite3
import pandas as pd

root = Path(__file__).resolve().parents[1]
with sqlite3.connect(":memory:") as db:
    predictions = pd.read_csv(root / "reports/holdout_predictions.csv")
    predictions.to_sql("predictions", db, index=False)
    result = pd.read_sql_query((root / "sql/monthly_error.sql").read_text(), db)
    mae, coverage = db.execute("SELECT AVG(ABS(ghi-prediction)), AVG(CASE WHEN ghi BETWEEN lower AND upper THEN 1.0 ELSE 0.0 END) FROM predictions").fetchone()
metrics = json.loads((root / "reports/metrics.json").read_text())
assert abs(mae - metrics["test"]["mae"]) < 1e-8
assert abs(coverage - metrics["coverage"]) < 1e-8
result.to_csv(root / "reports/sql_monthly_error.csv", index=False)
print(f"SQL verified MAE and coverage across {len(result)} location-months.")
