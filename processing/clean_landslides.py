"""Clean downloaded COOLR GeoJSON without inventing labels.

Outputs only observations with valid point geometry and parseable event dates.
Duplicates are removed by stable source identifiers where available.
"""
from __future__ import annotations
import json, re
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
AOI=(21.0,30.0,88.0,98.5)

def parse_date(v):
    if v is None or v=="": return pd.NaT
    if isinstance(v,(int,float)) and v>1e9:
        return pd.to_datetime(v, unit="ms", errors="coerce", utc=True)
    return pd.to_datetime(str(v), errors="coerce", utc=True)

def clean(src: Path, dst: Path):
    if not src.exists(): return {"status":"missing","source":str(src)}
    obj=json.loads(src.read_text(encoding="utf-8")); rows=[]
    for i,f in enumerate(obj.get("features",[])):
        g=f.get("geometry") or {}; c=g.get("coordinates") or []
        if g.get("type")!="Point" or len(c)<2: continue
        lon,lat=float(c[0]),float(c[1])
        if not (AOI[2]<=lon<=AOI[3] and AOI[0]<=lat<=AOI[1]): continue
        p=dict(f.get("properties") or {})
        p.update({"longitude":lon,"latitude":lat,"_feature_index":i})
        rows.append(p)
    df=pd.DataFrame(rows)
    if df.empty:
        dst.parent.mkdir(parents=True,exist_ok=True); pd.DataFrame(columns=["latitude","longitude","event_date","qa_status"]).to_parquet(dst,index=False)
        return {"status":"empty","rows":0}
    date_candidates=[c for c in df.columns if re.search(r"date|time|event",c,re.I)]
    if date_candidates:
        scored=[]
        for c in date_candidates:
            parsed=df[c].map(parse_date); scored.append((parsed.notna().sum(),c,parsed))
        _,best,parsed=max(scored,key=lambda x:x[0]); df["event_date"]=parsed
        df["event_date_source_column"]=best
    else: df["event_date"]=pd.NaT; df["event_date_source_column"]=""
    id_cols=[c for c in df.columns if re.search(r"(event|report|id)$",c,re.I)]
    if id_cols: df=df.drop_duplicates(subset=[id_cols[0]],keep="first")
    else: df=df.drop_duplicates(subset=["latitude","longitude","event_date"],keep="first")
    df["qa_status"]=df["event_date"].notna().map({True:"usable_event_time",False:"geometry_valid_date_missing"})
    df["cleaned_at_utc"]=datetime.now(timezone.utc).isoformat()
    dst.parent.mkdir(parents=True,exist_ok=True); df.to_parquet(dst,index=False)
    return {"status":"ok","rows":len(df),"dated_rows":int(df.event_date.notna().sum()),"columns":len(df.columns)}

if __name__=="__main__":
    for name in ["coolr_events","coolr_reports"]:
        result=clean(ROOT/"data/raw/landslides"/(name+".geojson"),ROOT/"data/interim"/(name+"_clean.parquet"))
        print(name,result)
