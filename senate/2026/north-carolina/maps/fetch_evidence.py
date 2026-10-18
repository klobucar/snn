"""Optional network refresh of URLs actually inspected on 2026-10-17/18.

Preserve the existing snapshot before running: upstream objects can change.
No geometry is downloaded from NC OneMap, avoiding a duplicate statewide asset.
"""
import concurrent.futures
import json
import urllib.parse
from source_io import ROOT, fetch

SOURCES = {
    "ncsbe-maps.html": "https://www.ncsbe.gov/results-data/voting-maps-redistricting",
    "ncsbe-folder.html": "https://dl.ncsbe.gov/?prefix=ShapeFiles/Precinct/",
    "ncsbe-list.js": "https://dl.ncsbe.gov/list.js",
    "ncsbe-precinct-list.xml": "https://s3.amazonaws.com/dl.ncsbe.gov?prefix=ShapeFiles%2FPrecinct%2F&max-keys=1000",
    "onemap-layer.json": "https://services.nconemap.gov/secure/rest/services/NC1Map_Boundaries/FeatureServer/0?f=pjson",
    "onemap-service.json": "https://services.nconemap.gov/secure/rest/services/NC1Map_Boundaries/FeatureServer?f=pjson",
    "onemap-metadata.xml": "https://services.nconemap.gov/secure/rest/services/NC1Map_Boundaries/FeatureServer/0/metadata",
    "onemap-item.json": "https://www.arcgis.com/sharing/rest/content/items/c27fef3332734c46827e3f07569997a8?f=pjson",
    "SBE_PRECINCTS_20240723.zip": "https://s3.amazonaws.com/dl.ncsbe.gov/ShapeFiles/Precinct/SBE_PRECINCTS_20240723.zip",
    "SBE_PRECINCTS_20260824.zip": "https://s3.amazonaws.com/dl.ncsbe.gov/ShapeFiles/Precinct/SBE_PRECINCTS_20260824.zip",
}

def main():
    # Independent requests; no agents or external publication.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        jobs = {pool.submit(fetch, "raw/" + name, url): name for name, url in SOURCES.items()}
        for job in concurrent.futures.as_completed(jobs):
            data = job.result()
            print(jobs[job], len(data))
    base = "https://services.nconemap.gov/secure/rest/services/NC1Map_Boundaries/FeatureServer/0/query?"
    queries = {
        "count": dict(where="1=1", returnCountOnly="true", f="json"),
        "ids": dict(where="1=1", returnIdsOnly="true", f="json"),
    }
    for page in range(2):
        queries[f"attributes-page-{page}"] = dict(where="1=1", outFields="*", returnGeometry="false",
            orderByFields="objectid", resultOffset=page * 2000, resultRecordCount=2000, f="json")
    for name, parameters in queries.items():
        fetch(f"raw/onemap-{name}.json.gz", base + urllib.parse.urlencode(parameters), True)
    # Reproduce the county-specific alternatives at their observed public URLs.
    for meta_path in sorted((ROOT / "raw").glob("*.meta.json")):
        name = meta_path.name.removesuffix(".meta.json")
        if name in SOURCES or name.startswith("onemap-"):
            continue
        meta=json.loads(meta_path.read_text())
        fetch("raw/" + name, meta["url"], meta.get("compression") == "gzip")

if __name__ == "__main__":
    main()
