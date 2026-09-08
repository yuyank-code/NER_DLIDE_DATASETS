"""Download public NER-SLIDE V6 source data with provenance manifests."""
from __future__ import annotations
import hashlib, json, sys, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import requests

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/"data/raw"; MANIFEST=ROOT/"manifests/acquisition_manifest.jsonl"
RAW.mkdir(parents=True,exist_ok=True); MANIFEST.parent.mkdir(parents=True,exist_ok=True)
AOI=dict(min_lat=21.0,max_lat=30.0,min_lon=88.0,max_lon=98.5)
HEADERS={"User-Agent":"NER-SLIDE-V6-data-pipeline/1.2"}
COOLR_BASE="https://gis.earthdata.nasa.gov/gis05/rest/services/Landslides"

def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def record(source:str,status:str,path:Path|None,url:str,**extra:Any)->None:
    row={"source":source,"status":status,"url":url,"retrieval_timestamp_utc":datetime.now(timezone.utc).isoformat(),"aoi":AOI,**extra}
    if path and path.exists(): row.update({"path":str(path.relative_to(ROOT)),"bytes":path.stat().st_size,"sha256":sha256(path)})
    with MANIFEST.open("a",encoding="utf-8") as f:f.write(json.dumps(row,sort_keys=True)+"\n")

def download(url:str,out:Path,source:str,timeout=1800)->bool:
    out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists() and out.stat().st_size>0: record(source,"already_present",out,url); return True
    tmp=out.with_suffix(out.suffix+".part")
    try:
        with requests.get(url,headers=HEADERS,stream=True,timeout=(30,timeout)) as r:
            r.raise_for_status()
            with tmp.open("wb") as f:
                for chunk in r.iter_content(1024*1024):
                    if chunk:f.write(chunk)
        tmp.replace(out); record(source,"downloaded",out,url); return True
    except Exception as e:
        if tmp.exists():tmp.unlink()
        record(source,"failed",None,url,error=repr(e)); print(f"FAILED {source}: {e}",file=sys.stderr); return False

def coolr(layer:str,source:str,filename:str)->bool:
    base=f"{COOLR_BASE}/{layer}/FeatureServer/0/query"
    out=RAW/"landslides"/filename; out.parent.mkdir(parents=True,exist_ok=True)
    features=[]; offset=0; page=2000
    while True:
        params={"where":"1=1","outFields":"*","returnGeometry":"true","f":"geojson","resultRecordCount":page,"resultOffset":offset,
                "geometry":f"{AOI['min_lon']},{AOI['min_lat']},{AOI['max_lon']},{AOI['max_lat']}","geometryType":"esriGeometryEnvelope","inSR":"4326","spatialRel":"esriSpatialRelIntersects","outSR":"4326"}
        try:
            r=requests.get(base,params=params,headers=HEADERS,timeout=120); r.raise_for_status(); obj=r.json()
            if "error" in obj: raise RuntimeError(obj["error"])
            batch=obj.get("features",[]); features.extend(batch)
            if len(batch)<page:break
            offset+=len(batch); time.sleep(.2)
        except Exception as e:
            record(source,"failed",None,r.url if 'r' in locals() else base,error=repr(e),records=len(features)); return False
    out.write_text(json.dumps({"type":"FeatureCollection","features":features},ensure_ascii=False),encoding="utf-8")
    record(source,"downloaded",out,base,records=len(features),spatial_filter=AOI,service="NASA Earthdata COOLR"); return True

def usgs()->bool:
    url="https://earthquake.usgs.gov/fdsnws/event/1/query"
    params={"format":"geojson","starttime":"2000-01-01","endtime":datetime.now(timezone.utc).date().isoformat(),"minmagnitude":2.5,
            "minlatitude":AOI["min_lat"],"maxlatitude":AOI["max_lat"],"minlongitude":AOI["min_lon"],"maxlongitude":AOI["max_lon"],"orderby":"time-asc","limit":20000}
    try:
        r=requests.get(url,params=params,headers=HEADERS,timeout=180); r.raise_for_status(); out=RAW/"seismic"/"usgs_earthquakes_2000_present.geojson"; out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(r.content)
        record("usgs_earthquakes","downloaded",out,r.url,query=params,records=len(r.json().get("features",[]))); return True
    except Exception as e:record("usgs_earthquakes","failed",None,url,error=repr(e)); return False

def worldcover()->int:
    """Download the 3x3-degree 2021 v200 tiles intersecting the NER AOI."""
    base="https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"; n=0
    for lat in (21,24,27):
        for lon in (87,90,93,96):
            tile=f"N{lat:02d}E{lon:03d}"; url=base+f"ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
            if download(url,RAW/"landcover"/(tile+"_Map.tif"),"worldcover_2021"): n+=1
    return n

def main()->int:
    print("Acquiring real public NER-SLIDE V6 datasets")
    coolr("COOLR_Events_Points","nasa_coolr_events","coolr_events.geojson")
    coolr("COOLR_Reports","nasa_coolr_reports","coolr_reports.geojson")
    usgs()
    download("https://download.geofabrik.de/asia/india/north-eastern-zone-latest.osm.pbf",RAW/"infrastructure"/"north-eastern-zone-latest.osm.pbf","osm_ne_india",3600)
    download("https://data.hydrosheds.org/file/hydrobasins/standard/hybas_as_lev01-12_v1c.zip",RAW/"hydrology"/"hydrobasins_as_lev01-12_v1c.zip","hydrobasins_asia",3600)
    download("https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_as_shp.zip",RAW/"hydrology"/"hydrorivers_asia.zip","hydrorivers_asia",3600)
    print(f"WorldCover tiles downloaded: {worldcover()}/12")
    print("Acquisition finished; inspect manifests/acquisition_manifest.jsonl for exact status and checksums.")
    return 0

if __name__=="__main__":raise SystemExit(main())
