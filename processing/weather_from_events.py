"""Build reproducible historical daily rainfall sequences around dated landslides.

Uses Open-Meteo's historical API as a public, reproducible weather source. The
query window ends at the event date, so no post-event rainfall enters predictors.
"""
from __future__ import annotations
import json, time
from pathlib import Path
import pandas as pd
import requests

ROOT=Path(__file__).resolve().parents[1]
API="https://archive-api.open-meteo.com/v1/archive"

def main():
    src=ROOT/"data/interim/coolr_events_clean.parquet"
    if not src.exists(): raise SystemExit("Run clean_landslides.py first")
    df=pd.read_parquet(src)
    df=df[df.event_date.notna()].copy()
    if df.empty: print("No dated events available"); return
    df["event_date"]=pd.to_datetime(df.event_date,utc=True)
    rows=[]
    for i,r in df.iterrows():
        d=r.event_date.date().isoformat(); start=(r.event_date-pd.Timedelta(days=30)).date().isoformat()
        params={"latitude":float(r.latitude),"longitude":float(r.longitude),"start_date":start,"end_date":d,
                "daily":"precipitation_sum,temperature_2m_mean,relative_humidity_2m_mean,wind_speed_10m_max,et0_fao_evapotranspiration",
                "timezone":"UTC"}
        try:
            j=requests.get(API,params=params,timeout=120).json()
            daily=j.get("daily",{})
            for k,date in enumerate(daily.get("time",[])):
                row={"event_index":int(r.get("_feature_index",i)),"event_date":d,"latitude":float(r.latitude),"longitude":float(r.longitude),"date":date}
                for v in ["precipitation_sum","temperature_2m_mean","relative_humidity_2m_mean","wind_speed_10m_max","et0_fao_evapotranspiration"]:
                    vals=daily.get(v,[]); row[v]=vals[k] if k<len(vals) else None
                rows.append(row)
        except Exception as e:
            rows.append({"event_index":int(r.get("_feature_index",i)),"event_date":d,"latitude":float(r.latitude),"longitude":float(r.longitude),"date":None,"error":repr(e)})
        if i%25==0: time.sleep(0.2)
    out=ROOT/"data/processed/event_weather_30d.parquet"; out.parent.mkdir(parents=True,exist_ok=True); pd.DataFrame(rows).to_parquet(out,index=False)
    print(f"Wrote {len(rows)} daily records to {out}")

if __name__=="__main__": main()
