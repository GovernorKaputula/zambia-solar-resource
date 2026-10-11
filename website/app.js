"use strict";
const study = JSON.parse(document.getElementById("study-data").textContent);
const $ = (id) => document.getElementById(id);
const months = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];
const fmt = (x, n = 0) =>
  Number(x).toLocaleString("en-GB", {
    minimumFractionDigits: n,
    maximumFractionDigits: n,
  });
const cities = Object.fromEntries(study.cities.map((c) => [c.name, c]));
let view = "monthly";
const line = (x1, y1, x2, y2, stroke, width = 1) =>
  `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${stroke}" stroke-width="${width}"/>`;
function chartResource(city, comparison) {
  const monthly = view === "monthly",
    values = monthly
      ? city.monthly.map((x) => x.mean)
      : city.years.map((x) => x.total);
  const other = comparison
    ? monthly
      ? comparison.monthly.map((x) => x.mean)
      : comparison.years.map((x) => x.total)
    : [];
  const labels = monthly ? months : city.years.map((x) => String(x.year));
  const ceiling = monthly
    ? 8
    : Math.ceil(Math.max(...values, ...other) / 500) * 500;
  const left = 54,
    right = 775,
    top = 22,
    bottom = 279,
    step = (right - left) / 12,
    y = (x) => bottom - (x / ceiling) * (bottom - top),
    x = (i) => left + step * (i + 0.5);
  let svg = "";
  for (let i = 0; i <= 4; i++) {
    const v = (ceiling * i) / 4;
    svg +=
      line(left, y(v), right, y(v), "#dce2d7") +
      `<text x="${left - 12}" y="${y(v) + 4}" text-anchor="end">${fmt(v, monthly ? 0 : 0)}</text>`;
  }
  values.forEach((v, i) => {
    svg += `<rect x="${x(i) - 16}" y="${y(v)}" width="32" height="${bottom - y(v)}" fill="#234d40"><title>${city.name}, ${labels[i]}: ${fmt(v, 2)}</title></rect>`;
    if (monthly) {
      const r = city.monthly[i];
      svg +=
        line(x(i), y(r.p10), x(i), y(r.p90), "#8a593b", 1.5) +
        line(x(i) - 5, y(r.p10), x(i) + 5, y(r.p10), "#8a593b", 1.5) +
        line(x(i) - 5, y(r.p90), x(i) + 5, y(r.p90), "#8a593b", 1.5);
    }
    svg += `<text x="${x(i)}" y="303" text-anchor="middle">${labels[i]}</text>`;
  });
  if (other.length) {
    svg += `<polyline fill="none" stroke="#b65732" stroke-width="2.5" points="${other.map((v, i) => `${x(i)},${y(v)}`).join(" ")}"/>`;
    other.forEach((v, i) => {
      svg += `<circle cx="${x(i)}" cy="${y(v)}" r="3.5" fill="#b65732"><title>${comparison.name}, ${labels[i]}: ${fmt(v, 2)}</title></circle>`;
    });
  }
  $("resource-chart").innerHTML = svg;
  $("chart-title").textContent =
    `${city.name} · ${monthly ? "monthly" : "annual"} solar resource`;
  $("chart-subtitle").textContent = monthly
    ? "Daily irradiation · kWh/m²/day"
    : "Annual irradiation · kWh/m²/year";
  $("chart-description").textContent = monthly
    ? "Bars show the mean of twelve annual monthly averages. Whiskers show the 10th–90th percentiles across years; these are variability ranges, not confidence intervals."
    : "Bars show the sum of daily irradiation in each calendar year. Year totals retain the extra day in leap years.";
  $("resource-caption").textContent =
    `${city.name}: ${monthly ? "monthly averages (kWh/m²/day)" : "annual totals (kWh/m²/year)"}`;
  $("resource-table").querySelector("thead").innerHTML =
    `<tr><th scope="col">${monthly ? "Month" : "Year"}</th><th scope="col">${city.name}</th>${monthly ? '<th scope="col">10th percentile</th><th scope="col">90th percentile</th>' : ""}${comparison ? `<th scope="col">${comparison.name}</th>` : ""}</tr>`;
  $("resource-table").querySelector("tbody").innerHTML = values
    .map(
      (v, i) =>
        `<tr><th scope="row">${labels[i]}</th><td>${fmt(v, 2)}</td>${monthly ? `<td>${fmt(city.monthly[i].p10, 2)}</td><td>${fmt(city.monthly[i].p90, 2)}</td>` : ""}${comparison ? `<td>${fmt(other[i], 2)}</td>` : ""}</tr>`,
    )
    .join("");
  $("legend-location").textContent = city.name;
  $("comparison-legend").hidden = !comparison;
  $("legend-compare").textContent = comparison ? comparison.name : "";
}
function scenario() {
  const city = cities[$("location").value],
    area = Number($("area").value),
    fraction = Number($("efficiency").value) / 100;
  $("area-label").textContent = `${area} m²`;
  $("efficiency-label").textContent = `${fmt(fraction * 100)}%`;
  $("energy-output").textContent = fmt(city.annual_mean * area * fraction);
}
function resource() {
  const city = cities[$("location").value],
    comparison = cities[$("compare").value];
  chartResource(city, comparison);
  $("coordinate").textContent =
    `${Math.abs(city.latitude).toFixed(4)}° S / ${city.longitude.toFixed(4)}° E`;
  $("annual-resource").textContent = fmt(city.annual_mean);
  $("daily-resource").textContent = `${fmt(city.daily_mean, 2)} kWh/m²/day`;
  const peak = city.monthly.reduce((a, b) => (a.mean > b.mean ? a : b)),
    low = city.monthly.reduce((a, b) => (a.mean < b.mean ? a : b));
  $("peak-month").textContent =
    `${months[peak.month - 1]} · ${fmt(peak.mean, 2)}`;
  $("low-month").textContent = `${months[low.month - 1]} · ${fmt(low.mean, 2)}`;
  $("annual-range").textContent =
    `${fmt(city.annual_min)}–${fmt(city.annual_max)} kWh/m²`;
  scenario();
}
function holdout() {
  const city = cities[$("holdout-location").value],
    values = city.holdout,
    left = 48,
    right = 975,
    bottom = 225,
    top = 20,
    ceil = 2.5,
    x = (i) => left + ((right - left) * i) / 23,
    y = (v) => bottom - (v / ceil) * (bottom - top);
  let svg = "";
  for (let v = 0; v <= 2.5; v += 0.5) {
    svg +=
      line(left, y(v), right, y(v), "#dce2d7") +
      `<text x="35" y="${y(v) + 4}" text-anchor="end">${v.toFixed(1)}</text>`;
  }
  ["baseline_mae", "mae"].forEach((key, k) => {
    const color = k ? "#b65732" : "#859d88";
    svg += `<polyline fill="none" stroke="${color}" stroke-width="${k ? 2.5 : 2}" points="${values.map((v, i) => `${x(i)},${y(v[key])}`).join(" ")}"/>`;
    values.forEach((v, i) => {
      svg += `<circle cx="${x(i)}" cy="${y(v[key])}" r="3" fill="${color}"><title>${v.month}: ${key === "mae" ? "selected model" : "climatology"} MAE ${fmt(v[key], 3)}</title></circle>`;
    });
  });
  values.forEach((v, i) => {
    if (i % 3 === 0 || i === 23)
      svg += `<text x="${x(i)}" y="251" text-anchor="middle">${months[Number(v.month.slice(5)) - 1]} ${v.month.slice(2, 4)}</text>`;
  });
  $("holdout-chart").innerHTML = svg;
  $("holdout-title").textContent = `${city.name} · error through the holdout`;
  $("holdout-table").querySelector("tbody").innerHTML = values
    .map(
      (v) =>
        `<tr><th scope="row">${v.month}</th><td>${fmt(v.mae, 3)}</td><td>${fmt(v.baseline_mae, 3)}</td><td>${fmt(v.coverage * 100, 1)}%</td></tr>`,
    )
    .join("");
}
["location", "compare"].forEach((id) =>
  $(id).addEventListener("change", resource),
);
document.querySelectorAll("[data-view]").forEach((button) =>
  button.addEventListener("click", () => {
    view = button.dataset.view;
    document
      .querySelectorAll("[data-view]")
      .forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
    resource();
  }),
);
["area", "efficiency"].forEach((id) =>
  $(id).addEventListener("input", scenario),
);
$("holdout-location").addEventListener("change", holdout);
resource();
holdout();
