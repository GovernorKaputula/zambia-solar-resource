# Data sources and measurement contract

Source: [NASA POWER daily point API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/), renewable-energy community (`RE`), local solar time (`LST`), 2014-01-01 through 2025-12-31.

The source responses, parameter definitions, returned metadata, retrieval timestamps, and SHA-256 digests are preserved in `data/raw/` and `data/provenance.json`. Acquisition was performed on 2026-10-11 UTC. Each location is requested once and then cached.

| Field | API parameter | Units | Interpretation |
| --- | --- | --- | --- |
| `ghi` | `ALLSKY_SFC_SW_DWN` | kWh/m²/day | Daily all-sky surface shortwave irradiation on a horizontal plane |
| `temperature` | `T2M` | °C | Daily average air temperature at 2 m |

The six city labels identify approximate reference coordinates, recorded in provenance. Returned values represent the underlying source grid; they are not station observations at those exact coordinates. See [NASA's source definitions, spatial caveats, and latency](https://power.larc.nasa.gov/docs/faqs/data/).

## Validation and transformations

- Verify the raw response checksum before using it.
- Require a unique, complete daily calendar for each location.
- Require the declared API units. Reject GHI outside 0–15 and temperature outside −20–50; these broad study-specific bounds catch missing sentinels and obvious corruption, not all source errors.
- Keep missing dates as errors; do not impute or treat them as zero.
- Build delayed features independently within each location. Eight days is the newest permissible lag.
- Use the first 28 days only as lag history; model rows start after this warmup.
- Resource summaries use the complete 2014–2025 panel. Model selection and calibration follow the separate chronology in the study.

NASA notes that archives can be revised. This study retains a fixed snapshot for reproducibility, and cannot reconstruct historical publication vintages from the current archive. Local solar time is the source time standard; it is not a claim that each day matches the civil-time boundary in Zambia.

## Attribution and reuse

Acknowledgement: data obtained from the NASA Langley Research Center POWER Project, supported through NASA's Earth Science / Applied Sciences program. See the [POWER referencing guide](https://power.larc.nasa.gov/docs/referencing/), [acknowledgements](https://power.larc.nasa.gov/docs/acknowledgements/), and [NASA data catalog entry](https://data.nasa.gov/dataset/prediction-of-worldwide-energy-resources-power).

The data remain attributed to NASA POWER. The repository's MIT license covers original code and is not a relicensing of the upstream data. This is independent work; NASA has not reviewed or endorsed it.
