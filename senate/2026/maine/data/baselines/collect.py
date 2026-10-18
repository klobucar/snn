#!/usr/bin/env python3
"""Capture bounded primary evidence, retaining original bytes losslessly.

Run without arguments for the named sources, or --id NAME --url URL to capture
a discovered link. No guessed candidate/contest identifiers. A www3 alternative
is explicit in each Maine request; source_url retains the originally linked URL.
"""
import argparse, datetime, gzip, hashlib, json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent
SOURCES = {
 'results-2024': 'https://www.maine.gov/sos/node/2479',
 'results-2022': 'https://www.maine.gov/sos/node/1956',
 'results-2020': 'https://www.maine.gov/sos/elections-voting/election-results-data/election-results-2020',
 'senate-2024': 'https://www.maine.gov/sos/sites/maine.gov.sos/files/inline-files/US Senator FINAL-Corrected 20241205.xlsx',
 'president-2024': 'https://www.maine.gov/sos/sites/maine.gov.sos/files/inline-files/President and Vice President FINAL-Corrected 20241205.xlsx',
 'governor-2022': 'https://www.maine.gov/sos/sites/maine.gov.sos/files/inline-files/Governor.xlsx',
 'clerk-2024': 'https://clerk.house.gov/member_info/electionInfo/2024/statistics2024.pdf',
 'clerk-2020': 'https://clerk.house.gov/member_info/electionInfo/2020/statistics2020.pdf',
 'nara-2024': 'https://www.archives.gov/files/electoral-college/2024/ascertainment-maine.pdf',
 'rcv-current': 'https://www.maine.gov/sos/elections-voting/upcoming/ranked-choice-voting-tabs',
 'rcv-statute': 'https://legislature.maine.gov/statutes/21-A/title21-Asec723-A.html',
 'certification-notice-2024': 'https://legislature.maine.gov/uploads/visual_edit/s-20250108.pdf',
 'governor-primary-archive-2022': 'https://lldc.mainelegislature.org/Open/Elections/Returns/2022/20221108/elec_20221108ad.pdf',
}

def capture(key, url):
    requested=url.replace('https://www.maine.gov/', 'https://www3.maine.gov/')
    when=datetime.datetime.now(datetime.timezone.utc).isoformat()
    with requests.get(requested, timeout=40, stream=True) as response:
        body=bytearray()
        for chunk in response.iter_content(65536):
            body.extend(chunk)
            if len(body)>=39_000_000: raise ValueError('bounded evidence request exceeded 39 MB')
        body=bytes(body)
        suffix='.xlsx' if body.startswith(b'PK') else '.pdf' if body.startswith(b'%PDF') else '.txt' if url.endswith('.txt') else '.html'
        name='raw/'+key+suffix+'.gz'
        (ROOT/'raw').mkdir(exist_ok=True)
        saved=gzip.compress(body,mtime=0)
        (ROOT/name).write_bytes(saved)
        return dict(source_id=key,source_url=url,request_url=requested,final_url=response.url,
                    retrieved_utc=when,http_status=response.status_code,
                    redirects=[dict(url=r.url,status=r.status_code,headers=dict(r.headers)) for r in response.history],
                    response_headers=dict(response.headers),original_bytes=len(body),
                    original_sha256=hashlib.sha256(body).hexdigest(),saved_path=name,
                    saved_bytes=len(saved),saved_sha256=hashlib.sha256(saved).hexdigest(),
                    encoding='gzip, lossless original response body',parser_version='maine-baselines-1')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--id');p.add_argument('--url');a=p.parse_args()
    manifest=ROOT/'manifest.json'
    old={x['source_id']:x for x in json.loads(manifest.read_text())} if manifest.exists() else {}
    sources={a.id:a.url or SOURCES[a.id]} if a.id else SOURCES
    for key,url in sources.items():
        item=capture(key,url);old[key]=item
        manifest.write_text(json.dumps(list(old.values()),indent=2)+'\n')
        print(key,item['http_status'],item['original_bytes'])
