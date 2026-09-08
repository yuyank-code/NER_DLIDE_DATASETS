"""Fail-fast data QA for acquired NER-SLIDE inputs."""
from __future__ import annotations
import json, sys
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
AOI=(21,30,88,98.5)
errors=[]
manifest=ROOT/"manifests/acquisition_manifest.jsonl"
if not manifest.exists(): errors.append("missing acquisition manifest")
else:
    rows=[json.loads(x) for x in manifest.read_text().splitlines() if x.strip()]
    for r in rows:
        if r.get("status") in {"downloaded","already_present"} and r.get("path"):
            p=ROOT/r["path"]
            if not p.exists() or p.stat().st_size==0: errors.append(f"manifest file missing/empty: {p}")
for p in [ROOT/"data/interim/coolr_events_clean.parquet",ROOT/"data/interim/coolr_reports_clean.parquet"]:
    if p.exists():
        d=pd.read_parquet(p)
        if not d.empty:
            if ((d.latitude<AOI[0])|(d.latitude>AOI[1])|(d.longitude<AOI[2])|(d.longitude>AOI[3])).any(): errors.append(f"AOI violation: {p}")
            if d[["latitude","longitude"]].isna().any().any(): errors.append(f"null coordinates: {p}")
            if d.duplicated(subset=["latitude","longitude","event_date"]).any(): errors.append(f"duplicate event coordinate/date rows: {p}")
if errors:
    print("DATA QA FAILED")
    print("\n".join(errors)); sys.exit(1)
print("DATA QA PASSED")
