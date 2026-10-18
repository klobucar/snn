#!/usr/bin/env python3
"""Download only public primary-source evidence into this owned directory.

Original response bodies are retained unchanged. Each response has retrieval
time, request/final URL, HTTP headers, byte count and SHA-256 in the manifest.
Usage: python3 fetch_evidence.py [saved_filename URL] (or default initial set).
"""
import datetime
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent
DEFAULT = {
    'ncsbe-historical-results.html': 'https://www.ncsbe.gov/results-data/election-results/historical-election-results-data',
    'layout_results_pct.txt': 'https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/layout_results_pct.txt',
    'results_pct_20241105.zip': 'https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/2024_11_05/results_pct_20241105.zip',
    'results_pct_20221108.zip': 'https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/2022_11_08/results_pct_20221108.zip',
    'certified-2024-contest.pdf': 'https://s3.amazonaws.com/dl.ncsbe.gov/State_Board_Meeting_Docs/2024-11-26/Canvass/Certification%20of%20State%20Jurisdiction%20Contests%20112624.pdf',
    'dashboard-2024.html': 'https://er.ncsbe.gov/?election_dt=11%2F05%2F2024',
    'certified-2022-contest.pdf': 'https://s3.amazonaws.com/dl.ncsbe.gov/State_Board_Meeting_Docs/2022-11-29/Canvass%20-%20Unofficial%20Abstracts/State_Composite_Abstract_Report-Contest.pdf',
    'national_county2020.txt': 'https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt',
    'ncsbe-voter-turnout.html': 'https://www.ncsbe.gov/results-data/voter-turnout',
    'ncsbe-2024-turnout.html': 'https://www.ncsbe.gov/results-data/voter-turnout/2024-general-election-turnout',
    'certified-2024-county.pdf': 'https://s3.amazonaws.com/dl.ncsbe.gov/State_Board_Meeting_Docs/2024-11-26/Canvass/Authentication%20of%20Composite%20Abstract%20112624.pdf',
    'certified-2022-county.pdf': 'https://s3.amazonaws.com/dl.ncsbe.gov/State_Board_Meeting_Docs/2022-11-29/Canvass%20-%20Unofficial%20Abstracts/State_Composite_Abstract_Report-County.pdf',
    'dashboard-2024-county.json': 'https://er.ncsbe.gov/enr/20241105/data/county.txt',
    'dashboard-2022-county.json': 'https://er.ncsbe.gov/enr/20221108/data/county.txt',
}

def main():
    if len(sys.argv) not in (1, 3):
        raise SystemExit(__doc__)
    sources = DEFAULT if len(sys.argv) == 1 else {sys.argv[1]: sys.argv[2]}
    path = ROOT / 'input-manifest.json'
    manifest = json.loads(path.read_text()) if path.exists() else {'sources': {}}
    for name, url in sources.items():
        assert Path(name).name == name
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        req = urllib.request.Request(url, headers={'User-Agent': 'NC-election-research/1.0 (public historical data)'})
        with urllib.request.urlopen(req, timeout=60) as response:
            data = response.read()
            entry = dict(url=url, final_url=response.url, retrieval_started_utc=started,
                         retrieved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                         http_status=response.status, http_headers=dict(response.headers),
                         bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                         saved_file=name, transformation='none; original response bytes')
        (ROOT / name).write_bytes(data)
        manifest['sources'][name] = entry
        path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        print(name, entry['http_status'], entry['bytes'], entry['sha256'])

if __name__ == '__main__':
    main()
