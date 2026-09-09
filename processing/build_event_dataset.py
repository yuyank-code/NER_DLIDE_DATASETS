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
EVENTS = ROOT / "data/interim/landslide_events_master.parquet"
OUT = ROOT / "data/processed/event_samples.parquet"

DYNAMIC = [
    "precipitation_sum", "temperature_2m_mean", "relative_humidity_2m_mean",
    "wind_speed_10m_max", "et0_fao_evapotranspiration",
]


def main() -> int:
    if not EVENTS.exists() or not WEATHER.exists():
        raise SystemExit("Missing canonical landslide events or event weather; run acquisition stages first")

    events = pd.read_parquet(EVENTS).copy()
    weather = pd.read_parquet(WEATHER).copy()
    events["event_date"] = pd.to_datetime(events["event_date"], utc=True, errors="coerce")
    weather["event_date"] = pd.to_datetime(weather["event_date"], utc=True, errors="coerce")
    weather["date"] = pd.to_datetime(weather["date"], utc=True, errors="coerce")
    weather = weather.dropna(subset=["event_date", "date", "event_index"])

    # Keep only events that survived canonical cleaning. The weather builder uses
    # event_index as the stable join key, while lat/lon/date are retained as
    # auditable spatial/temporal identifiers.
    valid = events[["event_index", "event_date", "latitude", "longitude", "source_dataset"]].copy()
    valid = valid.dropna(subset=["event_index", "event_date", "latitude", "longitude"])
    valid["event_index"] = valid["event_index"].astype(int)
    weather["event_index"] = pd.to_numeric(weather["event_index"], errors="coerce")
    weather = weather.dropna(subset=["event_index"])
    weather["event_index"] = weather["event_index"].astype(int)
    weather = weather.merge(valid, on="event_index", how="inner", suffixes=("", "_event"))
    if weather.empty:
        raise SystemExit("No weather rows matched canonical landslide events")

    # The weather window ends on the event date. We explicitly enforce this here
    # as a second leakage guard rather than trusting the upstream downloader.
    weather = weather[weather["date"] <= weather["event_date"]].copy()
    key = ["event_index", "event_date", "latitude", "longitude", "source_dataset"]
    rows = []
    for k, g in weather.groupby(key, dropna=False):
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
    out["predictor_cutoff_rule"] = "date <= event_date; no post-event observations"
    out["dataset_version"] = "v6-event-positive-v2"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False)
    summary = {
        "rows": int(len(out)),
        "unique_event_indices": int(out.event_index.nunique()),
        "date_min": out.event_date.min().isoformat(),
        "date_max": out.event_date.max().isoformat(),
        "labels": out.label.value_counts().to_dict(),
        "sources": out.source_dataset.value_counts().to_dict(),
        "sequence_length_min": int(out.sequence_length.min()),
        "sequence_length_median": float(out.sequence_length.median()),
        "sequence_length_max": int(out.sequence_length.max()),
        "note": "Positive event rows only. No unlabeled/unknown candidate was converted into a negative label."
    }
    (ROOT / "data/processed/event_dataset_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
