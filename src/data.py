"""Cached NASA POWER acquisition and strict daily-panel validation."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LOCATIONS = {
    "Lusaka": (-15.4167, 28.2833),
    "Livingstone": (-17.8419, 25.8543),
    "Ndola": (-12.9689, 28.6366),
    "Chipata": (-13.6333, 32.6500),
    "Kasama": (-10.2129, 31.1808),
    "Mongu": (-15.2484, 23.1274),
}
START, END = "2014-01-01", "2025-12-31"
PARAMETERS = {"ALLSKY_SFC_SW_DWN": "ghi", "T2M": "temperature"}


def download():
    folder = ROOT / "data" / "raw"
    folder.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / "data" / "provenance.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for city, (latitude, longitude) in LOCATIONS.items():
        path = folder / f"{city.lower()}.json"
        if path.exists():
            print(f"Using cached source: {city}", flush=True)
            continue
        query = urlencode({"parameters": ",".join(PARAMETERS), "community": "RE",
                           "latitude": latitude, "longitude": longitude,
                           "start": START.replace("-", ""), "end": END.replace("-", ""),
                           "format": "JSON", "time-standard": "LST"})
        url = "https://power.larc.nasa.gov/api/temporal/daily/point?" + query
        print(f"Downloading NASA POWER: {city}", flush=True)
        with urlopen(url, timeout=120) as response:
            raw = response.read()
        payload = json.loads(raw)
        assert "properties" in payload, payload
        path.write_bytes(raw)
        manifest[city] = {"url": url, "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                          "sha256": hashlib.sha256(raw).hexdigest(),
                          "file": path.relative_to(ROOT).as_posix(),
                          "parameters": payload["parameters"], "header": payload["header"],
                          "requested_coordinates": {"latitude": latitude, "longitude": longitude}}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def load():
    manifest = json.loads((ROOT / "data/provenance.json").read_text())
    parts = []
    expected = pd.date_range(START, END, freq="D")
    for city in LOCATIONS:
        record = manifest[city]
        raw = (ROOT / record["file"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == record["sha256"], f"Source changed: {city}"
        payload = json.loads(raw)
        assert payload["parameters"]["ALLSKY_SFC_SW_DWN"]["units"] == "kW-hr/m^2/day"
        assert payload["parameters"]["T2M"]["units"] == "C"
        frame = pd.DataFrame(payload["properties"]["parameter"]).rename(columns=PARAMETERS)
        frame.index = pd.to_datetime(frame.index, format="%Y%m%d")
        frame = frame.sort_index()
        assert frame.index.equals(expected), f"Incomplete or duplicate calendar: {city}"
        assert frame.ghi.between(0, 15).all(), f"Missing sentinel or invalid irradiance: {city}"
        assert frame.temperature.between(-20, 50).all(), f"Invalid temperature: {city}"
        frame.index.name = "date"
        frame["city"] = city
        parts.append(frame.reset_index())
    return pd.concat(parts, ignore_index=True)


if __name__ == "__main__":
    download()
    panel = load()
    panel.to_csv(ROOT / "data/daily.csv", index=False)
    print(f"Validated {len(panel):,} daily location records.")
