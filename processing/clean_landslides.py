"""Clean and merge public landslide inventories without inventing labels."""
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

def clean_geojson(src:Path,dst:Path,source_name:str):
    if not src.exists(): return pd.DataFrame()
    obj=json.loads(src.read_text(encoding="utf-8")); rows=[]
    for i,f in enumerate(obj.get("features",[])):
        g=f.get("geometry") or {}; c=g.get("coordinates") or []
        if g.get("type")!="Point" or len(c)<2: continue
        try: lon,lat=float(c[0]),float(c[1])
        except Exception: continue
        if not (AOI[2]<=lon<=AOI[3] and AOI[0]<=lat<=AOI[1]): continue
        p=dict(f.get("properties") or {}); p.update({"longitude":lon,"latitude":lat,"_feature_index":i,"source_dataset":source_name})
        rows.append(p)
    df=pd.DataFrame(rows)
    if df.empty: return df
    date_candidates=[c for c in df.columns if re.search(r"date|time|event",c,re.I)]
    parsed_cols=[]
    for c in date_candidates:
        parsed=df[c].map(parse_date); parsed_cols.append((int(parsed.notna().sum()),c,parsed))
    if parsed_cols:
        _,best,parsed=max(parsed_cols,key=lambda x:x[0]); df["event_date"]=parsed; df["event_date_source_column"]=best
    else: df["event_date"]=pd.NaT; df["event_date_source_column"]=""
    id_cols=[c for c in df.columns if re.search(r"(event|report|id)$",c,re.I)]
    if id_cols: df=df.drop_duplicates(subset=[id_cols[0]],keep="first")
    else: df=df.drop_duplicates(subset=["latitude","longitude","event_date"],keep="first")
    df["qa_status"]=df["event_date"].notna().map({True:"usable_event_time",False:"geometry_valid_date_missing"})
    df["cleaned_at_utc"]=datetime.now(timezone.utc).isoformat()
    dst.parent.mkdir(parents=True,exist_ok=True); df.to_parquet(dst,index=False)
    return df

def clean_glc(src:Path,dst:Path):
    if not src.exists(): return pd.DataFrame()
    df=pd.read_csv(src,low_memory=False)
    lower={c.lower():c for c in df.columns}
    lat=lower.get("latitude"); lon=lower.get("longitude")
    if not lat or not lon: return pd.DataFrame()
    df["latitude"]=pd.to_numeric(df[lat],errors="coerce"); df["longitude"]=pd.to_numeric(df[lon],errors="coerce")
    df=df[(df.latitude.between(AOI[0],AOI[1]))&(df.longitude.between(AOI[2],AOI[3]))].copy()
    date_col=next((lower[k] for k in lower if k in {"event_date","date","event date"}),None)
    df["event_date"]=df[date_col].map(parse_date) if date_col else pd.NaT
    df["source_dataset"]="NASA Global Landslide Catalog static export"
    df["_feature_index"]=range(len(df)); df["qa_status"]=df["event_date"].notna().map({True:"usable_event_time",False:"geometry_valid_date_missing"}); df["cleaned_at_utc"]=datetime.now(timezone.utc).isoformat()
    dst.parent.mkdir(parents=True,exist_ok=True); df.to_parquet(dst,index=False)
    return df

if __name__=="__main__":
    datasets=[]
    for name in ["coolr_events","coolr_reports"]:
        df=clean_geojson(ROOT/"data/raw/landslides"/(name+".geojson"),ROOT/"data/interim"/(name+"_clean.parquet"),"NASA COOLR "+name)
        print(name,{"rows":len(df),"dated_rows":int(df.event_date.notna().sum()) if not df.empty else 0})
        if not df.empty: datasets.append(df)
    glc=clean_glc(ROOT/"data/raw/landslides/global_landslide_catalog_export_2016.csv",ROOT/"data/interim/glc_clean.parquet")
    print("glc",{"rows":len(glc),"dated_rows":int(glc.event_date.notna().sum()) if not glc.empty else 0})
    if not glc.empty: datasets.append(glc)
    if datasets:
        master=pd.concat(datasets,ignore_index=True,sort=False)
        master=master[master.event_date.notna()].copy()
        master=master.drop_duplicates(subset=["latitude","longitude","event_date"],keep="first")
        master["event_index"]=range(len(master))
        out=ROOT/"data/interim/landslide_events_master.parquet"; out.parent.mkdir(parents=True,exist_ok=True); master.to_parquet(out,index=False)
        print("master",{"rows":len(master),"sources":master.source_dataset.value_counts().to_dict()})
    else:
        print("No public landslide inventory source produced usable dated NER events")
