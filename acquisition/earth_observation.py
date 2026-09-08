"""Acquire authoritative static earth-observation layers for the NER AOI.

No synthetic values are created. Each attempted file is recorded in the shared
acquisition manifest with retrieval metadata and SHA-256 when downloaded.
"""
from __future__ import annotations
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MANIFEST = ROOT / "manifests" / "acquisition_manifest.jsonl"
AOI = {"min_lat":21.0,"max_lat":30.0,"min_lon":88.0,"max_lon":98.5}
HEADERS={"User-Agent":"NER-SLIDE-V6-data-pipeline/1.0"}
TIMEOUT=(30,1800)

def sha256(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def record(source,status,path,url,**extra):
    row={"source":source,"status":status,"url":url,"retrieval_timestamp_utc":datetime.now(timezone.utc).isoformat(),"aoi":AOI,**extra}
    if path and path.exists(): row.update({"path":str(path.relative_to(ROOT)),"bytes":path.stat().st_size,"sha256":sha256(path)})
    MANIFEST.parent.mkdir(parents=True,exist_ok=True)
    with MANIFEST.open("a",encoding="utf-8") as f:f.write(json.dumps(row,sort_keys=True)+"\n")

def download(url,out,source,timeout=TIMEOUT):
    out=Path(out); out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists() and out.stat().st_size>0:
        record(source,"already_present",out,url); return True
    part=out.with_suffix(out.suffix+".part")
    try:
        with requests.get(url,headers=HEADERS,stream=True,timeout=timeout) as r:
            r.raise_for_status()
            with part.open("wb") as f:
                for chunk in r.iter_content(1024*1024):
                    if chunk:f.write(chunk)
        part.replace(out); record(source,"downloaded",out,url); return True
    except Exception as e:
        if part.exists():part.unlink()
        record(source,"failed",None,url,error=repr(e)); print(f"FAILED {source}: {e}",file=sys.stderr); return False

def worldcover():
    # WorldCover 2021 v200 is distributed as 3x3-degree EPSG:4326 COG tiles.
    for lat in range(21,30,3):
        for lon in range(87,99,3):
            tile=f"N{lat:02d}E{lon:03d}"
            url=f"https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
            download(url,RAW/"landcover"/f"worldcover_2021_{tile}_Map.tif","worldcover_2021")

def copernicus_dem():
    # Public AWS GLO-90 and GLO-30 buckets expose 1x1 degree COG tiles.
    # Use GLO-30 where a tile exists; GLO-90 is the guaranteed fallback.
    for lat in range(21,30):
        for lon in range(88,99):
            ns=f"N{lat:02d}"; ew=f"E{lon:03d}"
            for res,bucket in [(10,"copernicus-dem-30m"),(30,"copernicus-dem-90m")]:
                folder=f"Copernicus_DSM_COG_{res}_{ns}_00_{ew}_00_DEM"
                filename=f"{folder}.tif"
                url=f"https://{bucket}.s3.eu-central-1.amazonaws.com/{folder}/{filename}"
                ok=download(url,RAW/"dem"/filename,"copernicus_dem_glo30" if res==10 else "copernicus_dem_glo90",timeout=(30,600))
                if res==10 and ok: break

def soilgrids_vrts():
    # VRTs are authoritative virtual mosaics. They preserve the SoilGrids source
    # raster references and avoid committing a multi-terabyte global raster set.
    props=["clay","sand","silt","soc","phh2o","bdod","cfvo","nitrogen"]
    depths=["0-5cm","5-15cm","15-30cm","30-60cm","60-100cm","100-200cm"]
    for prop in props:
        for depth in depths:
            name=f"{prop}_{depth}_mean.vrt"
            url=f"https://files.isric.org/soilgrids/latest/data/{prop}/{prop}_{depth}_mean.vrt"
            download(url,RAW/"soil"/name,"soilgrids_2",timeout=(30,600))

def main():
    print("Acquiring WorldCover, Copernicus DEM and SoilGrids...")
    worldcover(); copernicus_dem(); soilgrids_vrts()

if __name__=="__main__": main()
