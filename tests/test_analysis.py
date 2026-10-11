"""Check information boundaries and audit saved evidence independently."""
import json
import unittest
import numpy as np
import pandas as pd
from src.data import ROOT, load
from src.analysis import FEATURES, features


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel = load()
        cls.pred = pd.read_csv(ROOT / "reports/holdout_predictions.csv", parse_dates=["date", "latest_input_date"])
        cls.metrics = json.loads((ROOT / "reports/metrics.json").read_text())

    def test_calendar_completeness_and_source_integrity(self):
        self.assertEqual(len(self.panel), 26298)
        self.assertFalse(self.panel.duplicated(["city", "date"]).any())
        self.assertEqual(self.panel.groupby("city").size().unique().tolist(), [4383])

    def test_information_cutoff_survives_future_perturbation(self):
        city = self.panel[self.panel.city == "Lusaka"].copy()
        date = pd.Timestamp("2024-06-01")
        before = features(city).set_index("date").loc[date, FEATURES].astype(float)
        modified = city.copy()
        modified.loc[modified.date > date - pd.Timedelta(days=8), ["ghi", "temperature"]] = 9999
        after = features(modified).set_index("date").loc[date, FEATURES].astype(float)
        np.testing.assert_array_equal(before, after)
        self.assertAlmostEqual(before["ghi_lag_8"], city.set_index("date").loc[date-pd.Timedelta(days=8), "ghi"])

    def test_holdout_metrics_reconcile(self):
        p, m = self.pred, self.metrics
        self.assertEqual(len(p), 4386)
        self.assertEqual(p.date.min(), pd.Timestamp("2024-01-01"))
        self.assertEqual(p.date.max(), pd.Timestamp("2025-12-31"))
        self.assertTrue(((p.date - p.latest_input_date).dt.days == 8).all())
        self.assertAlmostEqual(abs(p.ghi - p.prediction).mean(), m["test"]["mae"], places=8)
        self.assertAlmostEqual(abs(p.ghi - p.baseline).mean(), m["baseline"]["mae"], places=8)
        self.assertAlmostEqual(p.ghi.between(p.lower, p.upper).mean(), m["coverage"], places=8)
        self.assertTrue((p.lower >= 0).all())
        self.assertTrue((p.upper >= p.lower).all())

    def test_calibration_separate_and_intervals_reconcile(self):
        cal = pd.read_csv(ROOT / "reports/calibration_predictions.csv", parse_dates=["date"])
        self.assertTrue((cal.date.dt.year == 2023).all())
        for city in self.metrics["cities"]:
            rows = cal[cal.city == city["city"]]
            errors = sorted(abs(rows.ghi - rows.prediction))
            self.assertEqual(len(errors), 365)
            # ceil((365 + 1) * .8) = 293, one-based order statistic.
            radius = errors[292]
            self.assertAlmostEqual(radius, city["interval_radius"], places=8)
            test = self.pred[self.pred.city == city["city"]]
            np.testing.assert_allclose(test.upper, test.prediction + radius, atol=1e-8)
            np.testing.assert_allclose(test.lower, np.maximum(0, test.prediction - radius), atol=1e-8)

    def test_selection_uses_validation(self):
        candidates = pd.read_csv(ROOT / "reports/validation.csv")
        self.assertEqual(len(candidates), 30)
        expected = candidates.groupby("model").mae.mean().idxmin()
        self.assertEqual(expected, self.metrics["selected_model"])

    def test_explorer_matches_source(self):
        payload = json.loads((ROOT / "reports/explorer.json").read_text(encoding="utf-8"))
        for city in payload["cities"]:
            raw = self.panel[self.panel.city == city["name"]]
            self.assertAlmostEqual(raw.ghi.mean(), city["daily_mean"], places=9)
            self.assertAlmostEqual(raw.groupby(raw.date.dt.year).ghi.sum().mean(), city["annual_mean"], places=8)
            for month in city["monthly"]:
                subset = raw[raw.date.dt.month == month["month"]]
                yearly = subset.groupby(subset.date.dt.year).ghi.mean()
                self.assertAlmostEqual(yearly.mean(), month["mean"], places=8)
                self.assertAlmostEqual(yearly.quantile(.1), month["p10"], places=8)
                self.assertAlmostEqual(yearly.quantile(.9), month["p90"], places=8)


if __name__ == "__main__":
    unittest.main()
