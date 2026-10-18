#!/usr/bin/env python3
"""Fetch public primary evidence; preserve bytes, HTTP metadata and SHA-256."""
import argparse
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parent

def fetch(url, name):
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    req = urllib.request.Request(url, headers={"User-Agent": "OhioElectionResearch/1.0 (public certified historical results)", "Accept-Encoding": "identity"})
    try:
        response = urllib.request.urlopen(req, timeout=90)
    except urllib.error.HTTPError as err:
        response = err
    with response:
        body = response.read()
        record = {"requested_url": url, "final_url": response.url,
                  "retrieved_utc": started, "status": response.status,
                  "headers": dict(response.headers.items()), "path": name,
                  "uncompressed_bytes": len(body),
                  "sha256_original": hashlib.sha256(body).hexdigest()}
    stored = gzip.compress(body, mtime=0) if name.endswith(".gz") else body
    path.write_bytes(stored)
    record.update(bytes=len(stored), sha256=hashlib.sha256(stored).hexdigest())
    manifest = ROOT / "source-manifest.json"
    records = json.loads(manifest.read_text()) if manifest.exists() else []
    records = [r for r in records if r["path"] != name] + [record]
    manifest.write_text(json.dumps(records, indent=2) + "\n")
    print(json.dumps({k: record[k] for k in ("path", "status", "bytes", "final_url")}))
    return body

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("name")
    args = parser.parse_args()
    fetch(args.url, args.name)
