"""Build leakage-safe historical weather sequences around dated landslides."""
from __future__ import annotations
import time
from pathlib import Path
import pandas as pd
import requests

ROOT=Path(__file__).resolve().parents[1]
API="https://archive-api.open-meteo.com/v1/archive"
VARS=["precipitation_sum","temperature_2m_mean","relative_humidity_2m_mean","wind_speed_10m_max","et0_fao_evapotranspiration"]

def main():
    src=ROOT/"data/interim/landslide_events_master.parquet"
    if not src.exists(): raise SystemExit("Run clean_landslides.py first")
    df=pd.read_parquet(src); df=df[df.event_date.notna()].copy()
    if df.empty: raise SystemExit("No dated landslide events available")
    df["event_date"]=pd.to_datetime(df.event_date,utc=True)
    rows=[]
    for i,r in df.reset_index(drop=True).iterrows():
        d=r.event_date.date().isoformat(); start=(r.event_date-pd.Timedelta(days=30)).date().isoformat()
        params={"latitude":float(r.latitude),"longitude":float(r.longitude),"start_date":start,"end_date":d,"daily":",".join(VARS),"timezone":"UTC"}
        try:
            resp=requests.get(API,params=params,timeout=120); resp.raise_for_status(); daily=resp.json().get("daily",{})
            for k,date in enumerate(daily.get("time",[])):
                row={"event_index":int(r.event_index),"event_date":d,"latitude":float(r.latitude),"longitude":float(r.longitude),"date":date,"source_dataset":r.source_dataset}
                for v in VARS:
                    vals=daily.get(v,[]); row[v]=vals[k] if k<len(vals) else None
                rows.append(row)
        except Exception as e:
            rows.append({"event_index":int(r.event_index),"event_date":d,"latitude":float(r.latitude),"longitude":float(r.longitude),"date":None,"source_dataset":r.source_dataset,"error":repr(e)})
        if i%25==0: time.sleep(0.2)
    out=ROOT/"data/processed/event_weather_30d.parquet"; out.parent.mkdir(parents=True,exist_ok=True); pd.DataFrame(rows).to_parquet(out,index=False)
    print(f"Wrote {len(rows)} daily records for {len(df)} landslide events")

if __name__=="__main__": main()
