"""Lossless HTTP evidence snapshots; all writes are confined to this directory."""
from pathlib import Path
import datetime
import gzip
import hashlib
import json
import urllib.request

ROOT = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def fetch(relative, url, compress=False):
    target = ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "NC-precinct-research/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
        meta = dict(url=url, final_url=response.url, status=response.status,
                    retrieved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    headers=dict(response.headers), bytes=len(data), sha256=sha(data))
    stored = gzip.compress(data, mtime=0) if compress else data
    target.write_bytes(stored)
    meta.update(stored_bytes=len(stored), stored_sha256=sha(stored), compression="gzip" if compress else None)
    target.with_name(target.name + ".meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    return data

def read(relative):
    target = ROOT / relative
    data = target.read_bytes()
    meta = json.loads(target.with_name(target.name + ".meta.json").read_text())
    assert sha(data) == meta.get("stored_sha256", meta["sha256"]), target
    if meta.get("compression") == "gzip":
        data = gzip.decompress(data)
    assert sha(data) == meta["sha256"], target
    return data

def get_json(relative, url=None, compress=False):
    return json.loads(fetch(relative, url, compress) if url else read(relative))
