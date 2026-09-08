# NER-SLIDE DATA

Real-data acquisition, validation, provenance, and dataset construction for the NER-SLIDE V6 landslide early-warning research system.

## Purpose

This repository is the data side of NER-SLIDE V6. It downloads public authoritative/research datasets, keeps immutable raw inputs out of Git history, records provenance and checksums, validates coverage/geometry/time, and produces reproducible intermediate data.

**No synthetic values are generated. Unknown observations remain unknown.**

## Run locally

```bash
python -m pip install -r requirements.txt
python acquisition/acquire.py
python processing/clean_landslides.py
```

Set optional credentials only for providers that require them. Public sources run without credentials.

## GitHub Actions

The workflow in `.github/workflows/acquire.yml` downloads the public datasets into the workflow workspace and publishes compressed artifacts. Large raw files are intentionally not committed to Git.

## Data principles

1. Prediction-time leakage is prohibited.
2. Raw files are immutable after acquisition.
3. Every source gets URL, release/version, retrieval timestamp, observation period, spatial resolution, CRS, coverage, checksum, and QA status.
4. Confirmed event, confirmed usable negative, and unknown are separate states.
5. Historical research products and low-latency operational products are tracked separately.
6. A candidate feature enters the final model only after leakage-safe ablation and fixed evaluation tests.

## Initial source universe

- NASA COOLR landslide reports/events
- ISRO/NRSC/Bhuvan Landslide Atlas inventories (where programmatic access is available)
- USGS earthquake catalog
- OpenStreetMap North-Eastern India extract
- ESA WorldCover
- ISRIC SoilGrids
- HydroSHEDS HydroBASINS/HydroRIVERS
- NASA GPM IMERG
- Open-Meteo/ERA5-Land weather reanalysis
- Copernicus DEM (credentialed/public distribution paths as applicable)
- Sentinel-1 and Sentinel-2 through Copernicus Data Space (credentialed API path)

See `config/sources.json` for exact source metadata and access modes.
