"""Build the first canonical event-time dataset from real cleaned observations.

This stage deliberately produces positive/event rows and unknown candidate rows
separately. It never converts an unobserved date into a negative label.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WEATHER = ROOT / "data/processed/event_weather_30d.parquet"
EVENTS = ROOT / "data/interim/coolr_events_clean.parquet"
OUT = ROOT / "data/processed/event_samples.parquet"

DYNAMIC = [
    "precipitation_sum", "temperature_2m_mean", "relative_humidity_2m_mean",
    "wind_speed_10m_max", "et0_fao_evapotranspiration",
]


def main() -> int:
    if not EVENTS.exists() or not WEATHER.exists():
        raise SystemExit("Missing cleaned events or event weather; run acquisition stages first")
    events = pd.read_parquet(EVENTS).copy()
    weather = pd.read_parquet(WEATHER).copy()
    events["event_date"] = pd.to_datetime(events["event_date"], utc=True, errors="coerce")
    weather["event_date"] = pd.to_datetime(weather["event_date"], utc=True, errors="coerce")
    weather["date"] = pd.to_datetime(weather["date"], utc=True, errors="coerce")
    weather = weather.dropna(subset=["event_date", "date"])

    # Join by the stable source feature index and event date. The weather window
    # ends on the event date, so predictors cannot use post-event observations.
    key = ["event_index", "event_date", "latitude", "longitude"]
    w = weather.groupby(key, dropna=False)
    rows = []
    for k, g in w:
        g = g.sort_values("date").tail(31).copy()
        row = {name: value for name, value in zip(key, k)}
        row["label"] = 1
        row["label_status"] = "confirmed_inventory_event"
        row["sequence_length"] = int(len(g))
        row["sequence_start"] = g["date"].min()
        row["sequence_end"] = g["date"].max()
        row["event_timestamp"] = k[1]
        for v in DYNAMIC:
            x = pd.to_numeric(g[v], errors="coerce").to_numpy(dtype=float)
            row[f"{v}_missing_fraction"] = float(np.mean(~np.isfinite(x))) if len(x) else 1.0
            row[f"{v}_sum_30d"] = float(np.nansum(x)) if len(x) else np.nan
            row[f"{v}_max_3d"] = float(np.nanmax(x[-3:])) if len(x) and np.isfinite(x[-3:]).any() else np.nan
            row[f"{v}_max_7d"] = float(np.nanmax(x[-7:])) if len(x) and np.isfinite(x[-7:]).any() else np.nan
        rows.append(row)

    out = pd.DataFrame(rows)
    if out.empty:
        raise SystemExit("No usable event-time samples were produced")
    out["source_dataset"] = "NASA COOLR + Open-Meteo historical"
    out["predictor_cutoff_rule"] = "date <= event_date; no post-event observations"
    out["dataset_version"] = "v6-event-positive-v1"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False)
    summary = {
        "rows": int(len(out)),
        "unique_event_indices": int(out.event_index.nunique()),
        "date_min": out.event_date.min().isoformat(),
        "date_max": out.event_date.max().isoformat(),
        "labels": out.label.value_counts().to_dict(),
        "note": "This is not yet a supervised positive/negative training set; unknown candidate windows remain unlabeled."
    }
    (ROOT / "data/processed/event_dataset_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
