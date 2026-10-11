"""Chronological model selection, calibration, and an untouched two-year test."""
import json
import math
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from .data import ROOT, LOCATIONS, load

SEED = 42
ALPHA = 0.20
CANDIDATES = ["monthly_climatology", "seasonal_harmonics", "delayed_ridge", "boosting_7", "boosting_15"]
CALENDAR = [f"{kind}_{n}" for n in range(1, 4) for kind in ["sin", "cos"]]
LAGGED = [f"{field}_lag_{lag}" for field in ["ghi", "temperature"] for lag in [8, 14, 21, 28]]
FEATURES = CALENDAR + LAGGED + ["ghi_prior_mean", "ghi_prior_std"]


def features(panel):
    parts = []
    for _, group in panel.groupby("city", sort=True):
        frame = group.sort_values("date").copy()
        phase = 2 * np.pi * (frame.date.dt.dayofyear - 1) / 365.2425
        for n in range(1, 4):
            frame[f"sin_{n}"], frame[f"cos_{n}"] = np.sin(n * phase), np.cos(n * phase)
        for field in ["ghi", "temperature"]:
            for lag in [8, 14, 21, 28]:
                frame[f"{field}_lag_{lag}"] = frame[field].shift(lag)
        frame["ghi_prior_mean"] = frame.ghi.shift(8).rolling(7).mean()
        frame["ghi_prior_std"] = frame.ghi.shift(8).rolling(7).std()
        frame["latest_input_date"] = frame.date - pd.Timedelta(days=8)
        parts.append(frame.dropna(subset=FEATURES))
    return pd.concat(parts, ignore_index=True)


def fit_predict(name, train, target):
    if name == "monthly_climatology":
        means = train.groupby(train.date.dt.month).ghi.mean()
        return target.date.dt.month.map(means).to_numpy()
    if name in ["seasonal_harmonics", "delayed_ridge"]:
        columns = CALENDAR if name == "seasonal_harmonics" else FEATURES
        model = make_pipeline(StandardScaler(), Ridge(alpha=10))
    else:
        columns = FEATURES
        model = HistGradientBoostingRegressor(max_leaf_nodes=int(name.split("_")[1]),
                    max_iter=150, learning_rate=0.05, l2_regularization=5,
                    early_stopping=False, random_state=SEED)
    model.fit(train[columns], train.ghi)
    return np.maximum(0, model.predict(target[columns]))


def score(actual, prediction):
    error = np.asarray(prediction) - np.asarray(actual)
    return {"mae": float(np.abs(error).mean()), "rmse": float(np.sqrt((error**2).mean())),
            "bias": float(error.mean())}


def interval_radius(residuals, alpha=ALPHA):
    residuals = np.sort(np.asarray(residuals))
    rank = min(len(residuals), math.ceil((len(residuals) + 1) * (1 - alpha)))
    return float(residuals[rank - 1])


def block_skill_interval(predictions):
    daily = predictions.assign(model_error=lambda x: abs(x.prediction - x.ghi),
                               baseline_error=lambda x: abs(x.baseline - x.ghi))
    errors = daily.groupby("date")[["model_error", "baseline_error"]].mean().to_numpy()
    rng, n = np.random.default_rng(SEED), len(errors)
    samples = []
    # Resample shared dates for all locations; preserve short runs with circular 7-day blocks.
    for _ in range(2000):
        starts = rng.integers(0, n, size=math.ceil(n / 7))
        indices = ((starts[:, None] + np.arange(7)) % n).ravel()[:n]
        model, baseline = errors[indices].mean(axis=0)
        samples.append(100 * (1 - model / baseline))
    return [float(x) for x in np.quantile(samples, [0.025, 0.975])]


def run():
    output = ROOT / "reports"
    output.mkdir(exist_ok=True)
    panel = load()
    panel.to_csv(ROOT / "data/daily.csv", index=False, float_format="%.8f")
    design = features(panel)
    validation = []
    for city, frame in design.groupby("city", sort=True):
        train, valid = frame[frame.date < "2021-01-01"], frame[frame.date.between("2021-01-01", "2022-12-31")]
        for name in CANDIDATES:
            prediction = fit_predict(name, train, valid)
            validation.append({"city": city, "model": name, **score(valid.ghi, prediction)})
    validation = pd.DataFrame(validation)
    leaderboard = validation.groupby("model").mae.mean().sort_values(kind="stable")
    selected = str(leaderboard.index[0])
    validation.to_csv(output / "validation.csv", index=False)
    print(f"Validation selected {selected}: MAE {leaderboard.iloc[0]:.4f}", flush=True)
    final, calibration_rows, city_results = [], [], []
    for city, frame in design.groupby("city", sort=True):
        train = frame[frame.date < "2023-01-01"]
        cal = frame[frame.date.between("2023-01-01", "2023-12-31")].copy()
        test = frame[frame.date >= "2024-01-01"].copy()
        # One fixed fit; calibration outcomes never enter model fitting.
        target = pd.concat([cal, test])
        prediction = fit_predict(selected, train, target)
        cal["prediction"] = prediction[:len(cal)]
        radius = interval_radius(abs(cal.prediction - cal.ghi))
        test["prediction"] = prediction[len(cal):]
        test["baseline"] = fit_predict("monthly_climatology", train, test)
        test["persistence"] = test.ghi_lag_8
        test["lower"] = np.maximum(0, test.prediction - radius)
        test["upper"] = test.prediction + radius
        test["covered"] = test.ghi.between(test.lower, test.upper)
        test["season"] = np.where(test.date.dt.month.isin([11, 12, 1, 2, 3, 4]), "Nov-Apr", "May-Oct")
        final.append(test[["city", "date", "latest_input_date", "ghi", "prediction", "baseline",
                           "persistence", "lower", "upper", "covered", "season"]])
        calibration_rows.append(cal[["city", "date", "ghi", "prediction"]])
        city_results.append({"city": city, "rows": len(test), "model": score(test.ghi, test.prediction),
                             "baseline": score(test.ghi, test.baseline), "interval_radius": radius,
                             "coverage": float(test.covered.mean())})
    predictions = pd.concat(final, ignore_index=True)
    calibration = pd.concat(calibration_rows, ignore_index=True)
    predictions.to_csv(output / "holdout_predictions.csv", index=False, float_format="%.10f")
    calibration.to_csv(output / "calibration_predictions.csv", index=False, float_format="%.10f")
    model_score, base_score = score(predictions.ghi, predictions.prediction), score(predictions.ghi, predictions.baseline)
    seasons = [{"season": name, "rows": len(group), "model": score(group.ghi, group.prediction),
                "baseline": score(group.ghi, group.baseline), "coverage": float(group.covered.mean())}
               for name, group in predictions.groupby("season")]
    summary = {
        "period": {"start": "2014-01-01", "end": "2025-12-31"}, "rows": len(panel),
        "locations": len(LOCATIONS), "unit": "kWh/m²/day", "input_delay_days": 8,
        "selected_model": selected, "validation_leaderboard": leaderboard.to_dict(),
        "split": {"initial_fit": "2014-2020", "validation": "2021-2022",
                  "refit": "2014-2022", "calibration": "2023", "holdout": "2024-2025"},
        "test_rows": len(predictions), "test": model_score, "baseline": base_score,
        "persistence": score(predictions.ghi, predictions.persistence),
        "skill_pct": 100 * (1 - model_score["mae"] / base_score["mae"]),
        "skill_95_block_interval": block_skill_interval(predictions),
        "nominal_coverage": 1 - ALPHA, "coverage": float(predictions.covered.mean()),
        "mean_interval_width": float((predictions.upper - predictions.lower).mean()),
        "cities": city_results, "seasons": seasons,
    }
    (output / "metrics.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    build_explorer_data(panel, predictions, summary)
    plots(panel, predictions, summary)
    write_report(summary)
    print(json.dumps({k: summary[k] for k in ["test", "baseline", "skill_pct", "coverage"]}, indent=2))


def build_explorer_data(panel, predictions, summary):
    cities = []
    monthly_rows = []
    for city, (lat, lon) in LOCATIONS.items():
        frame = panel[panel.city == city].copy()
        frame["month"], frame["year"] = frame.date.dt.month, frame.date.dt.year
        month_year = frame.groupby(["year", "month"]).ghi.mean().reset_index()
        monthly = []
        for month, group in month_year.groupby("month"):
            record = {"month": int(month), "mean": float(group.ghi.mean()),
                      "p10": float(group.ghi.quantile(0.1)), "p90": float(group.ghi.quantile(0.9))}
            monthly.append(record)
            monthly_rows.append({"city": city, **record})
        annual = frame.groupby("year").ghi.sum()
        test = predictions[predictions.city == city].copy()
        monthly_test = test.assign(month=test.date.dt.strftime("%Y-%m")).groupby("month")
        history = [{"month": month, "actual": float(g.ghi.mean()), "prediction": float(g.prediction.mean()),
                    "mae": float(abs(g.prediction - g.ghi).mean()), "baseline_mae": float(abs(g.baseline - g.ghi).mean()),
                    "coverage": float(g.covered.mean())} for month, g in monthly_test]
        yearly = [{"year": int(year), "total": float(total)} for year, total in annual.items()]
        cities.append({"name": city, "latitude": lat, "longitude": lon, "monthly": monthly,
                       "annual_mean": float(annual.mean()), "daily_mean": float(frame.ghi.mean()),
                       "annual_min": float(annual.min()), "annual_max": float(annual.max()),
                       "years": yearly, "holdout": history,
                       "evaluation": next(c for c in summary["cities"] if c["city"] == city)})
    pd.DataFrame(monthly_rows).to_csv(ROOT / "reports/monthly_resource.csv", index=False)
    (ROOT / "reports/explorer.json").write_text(json.dumps({"summary": summary, "cities": cities},
                                                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def plots(panel, predictions, summary):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.labelcolor": "#183d37", "text.color": "#183d37",
                         "axes.edgecolor": "#cbd3cd", "figure.facecolor": "#f6f5ee", "axes.facecolor": "#f6f5ee"})
    colors = ["#193e36", "#bb613c", "#658471", "#ab933a", "#6c7893", "#765c69"]
    fig, ax = plt.subplots(figsize=(10, 4.5), layout="constrained")
    for (city, group), color in zip(panel.groupby("city"), colors):
        monthly = group.groupby(group.date.dt.month).ghi.mean()
        ax.plot(monthly.index, monthly, label=city, color=color, linewidth=2)
    ax.set(xticks=range(1, 13), xticklabels=list("JFMAMJJASOND"), ylabel="Daily solar irradiation (kWh/m²/day)",
           title="A seasonal resource, across six locations · 2014–2025")
    ax.legend(ncol=3, frameon=False, loc="lower center")
    fig.savefig(ROOT / "reports/seasonality.svg")
    fig.savefig(ROOT / "reports/seasonality.png", dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 4.5), layout="constrained")
    names = [c["city"] for c in summary["cities"]]
    x = np.arange(len(names))
    ax.bar(x - .18, [c["baseline"]["mae"] for c in summary["cities"]], .34, color="#b6c4b9", label="Monthly climatology")
    ax.bar(x + .18, [c["model"]["mae"] for c in summary["cities"]], .34, color="#bb613c", label="Selected model")
    ax.set(xticks=x, xticklabels=names, ylabel="Mean absolute error (kWh/m²/day)", title="The final test · 2024–2025")
    ax.legend(frameon=False)
    fig.savefig(ROOT / "reports/holdout.svg")
    plt.close(fig)


def write_report(m):
    cities = "\n".join(f'| {c["city"]} | {c["model"]["mae"]:.3f} | {c["baseline"]["mae"]:.3f} | {c["coverage"]:.1%} |' for c in m["cities"])
    candidates = "\n".join(f'| {name} | {value:.4f} |' for name, value in m["validation_leaderboard"].items())
    text = f'''# Zambia solar resources: seasonality and a delayed-input forecast benchmark

Kenneth Gondwe Kaputula · Independent analysis · 2014–2025 source window

## Question and scope

How does the solar resource vary across six Zambian locations, and how much can a statistical forecast improve on a seasonal expectation when recent observations arrive late?

NASA POWER supplies daily global horizontal irradiation (GHI) and near-surface air temperature at reference coordinates for Lusaka, Livingstone, Ndola, Chipata, Kasama, and Mongu. These are gridded satellite/model-derived estimates. The study contains {m["rows"]:,} daily location records with a complete calendar and no missing-value sentinels. The resource summary uses 2014–2025; model fitting uses the separate chronology below.

![Seasonal resource](seasonality.svg)

## Evaluation protocol

1. Train candidates on 2014–2020 after a 28-day feature warmup.
2. Select one model family across all cities using pooled MAE on 2021–2022. Each city has its own fitted model.
3. Refit the selected family on 2014–2022, with no later refit.
4. Use 2023 absolute residuals to calibrate a separate 80% interval radius for each city.
5. Evaluate fixed models and radii once on 2024–2025 ({m["test_rows"]:,} location-days).

Candidate definitions are fixed in source: month-of-year means; three annual Fourier harmonics with Ridge alpha 10; those harmonics plus delayed solar/temperature features with Ridge alpha 10; and two histogram boosting models with 7 or 15 leaves, 150 iterations, learning rate .05, L2 regularization 5, and no random early-stopping split. Negative forecasts are clipped at zero. All learned transformations fit on the training slice only.

| Candidate | Validation MAE (kWh/m²/day) |
| --- | ---: |
{candidates}

The globally selected family is **{m["selected_model"]}**. Candidate hyperparameters were not searched on the final test. Monthly climatology and an eight-day persistence benchmark remain in the final comparison even when they lose validation.

## Availability matters

Every non-calendar input is at least eight days older than its prediction date. Features include solar and temperature lags of 8, 14, 21, and 28 days, plus the mean and standard deviation of solar values from t−14 through t−8. No same-day weather is used. The source documents roughly 5–7 days of solar latency; an eight-day cutoff is an explicit assumption, not evidence that every historical release met it. Archived data may have been revised, and historical publication vintages were unavailable. This is a retrospective benchmark, not an operational forecast service.

## Final results

Selected-model MAE is **{m["test"]["mae"]:.3f} kWh/m²/day**, versus **{m["baseline"]["mae"]:.3f}** for monthly climatology and **{m["persistence"]["mae"]:.3f}** for eight-day persistence. Relative MAE reduction versus climatology is **{m["skill_pct"]:.2f}%**; the paired circular seven-day block bootstrap interval is **{m["skill_95_block_interval"][0]:.2f}% to {m["skill_95_block_interval"][1]:.2f}%** (2,000 draws, seed 42). Shared dates are sampled across all locations, preserving spatial pairing. This interval describes sampling sensitivity within this period, not source-product uncertainty or performance in a new climate.

![Held-out forecast error](holdout.svg)

| Location | Model MAE | Climatology MAE | 80% interval coverage |
| --- | ---: | ---: | ---: |
{cities}

Overall empirical coverage is **{m["coverage"]:.1%}** at a nominal 80%; mean interval width is **{m["mean_interval_width"]:.3f} kWh/m²/day**. The radius is the finite-sample corrected 80th percentile of 2023 absolute residuals, with the lower endpoint clipped to zero. Temporal dependence and distribution changes violate simple exchangeability assumptions; nominal coverage is a target, not a guarantee. Seasonal error and coverage are exported in `metrics.json`.

## What the explorer shows

Monthly bars are averages of the twelve annual monthly means; their whiskers are the 10th–90th percentiles across those twelve years. They describe interannual variability, not a confidence interval. Annual summaries are daily GHI sums averaged over years. The explorer's area/efficiency scenario multiplies irradiation by collecting area and a chosen net conversion fraction. It is a simple horizontal-plane energy calculation, not a validated PV yield model: tilt, shading, thermal behavior, inverter clipping, storage, and demand are not modeled.

## Limits and next evidence

- Six reference coordinates represent source grid cells, not local sensor installations. Nearby-site rankings should not be interpreted as precise engineering siting advice.
- Errors measure agreement with NASA POWER estimates, not with ground truth from a pyranometer or inverter.
- Calendar features can describe seasonality without anticipating unusual cloud conditions. The failed or weaker candidates remain in the validation table.
- A real forecasting deployment needs a dated archive of data availability, weather forecast inputs, and forward-only monitoring. This study does not claim electricity savings, project revenue, client outcomes, or grid reliability effects.
- The strongest extension is a permissioned local irradiance or generation series, then evaluation of bias, missingness, seasonal errors, and source-to-sensor disagreement.

## Reproduce and audit

Run `python -m src.analysis` against the committed source snapshots, then `python -m unittest discover -s tests -v` and `python scripts/sql_audit.py`. SHA-256 digests and exact request URLs are in `data/provenance.json`; predictions and calibration residual inputs are committed. `docs/index.html` is built by `python build.py`.

Data acknowledgement: NASA Langley Research Center POWER Project, funded through the NASA Earth Science Directorate Applied Science Program. Sources: [POWER daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/), [data definitions and latency](https://power.larc.nasa.gov/docs/faqs/data/), [methodology](https://power.larc.nasa.gov/docs/methodology/). No NASA endorsement is implied.
'''
    (ROOT / "reports/study.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    run()
