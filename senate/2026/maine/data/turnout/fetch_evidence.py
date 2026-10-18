#!/usr/bin/env python3
"""Bounded public-source capture. No crawler, pagination or guessed election IDs.

Each named source is fetched once (30s timeout, 38 MiB cap); redirects, headers,
original URL, tested alternate host, UTC time and original-byte hashes survive.
Use --only ID ... to avoid refreshing unrelated evidence. Requires requests.
"""
import argparse, datetime, gzip, hashlib, json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent
BASE = 'https://www.maine.gov'
FILES = {
 'results-index': '/sos/elections-voting/election-results-data/previous-election-results',
 'results-2024': '/sos/node/2479',
 'results-2022': '/sos/node/1956',
 'enrollment-index': '/sos/elections-voting/voter-data/previous-enrollment-data',
 'senate-2024': '/sos/sites/maine.gov.sos/files/inline-files/US Senator FINAL-Corrected 20241205.xlsx',
 'president-2024': '/sos/sites/maine.gov.sos/files/inline-files/President and Vice President FINAL-Corrected 20241205.xlsx',
 'governor-2022': '/sos/sites/maine.gov.sos/files/inline-files/Governor.xlsx',
 'registration-2024-active': '/sos/sites/maine.gov.sos/files/inline-files/Reg & Enr as of 11-5-24 txt (A).txt',
 'registration-2024-inactive': '/sos/sites/maine.gov.sos/files/inline-files/Reg & Enr as of 11-5-24 txt (I).txt',
 'registration-2022-active': '/sos/sites/maine.gov.sos/files/data-text/r-e-active111822.txt',
 'registration-2022-inactive': '/sos/sites/maine.gov.sos/files/data-text/r-e-inact111822.txt',
 'registration-layout-2024': '/sos/elections-voting/voter-data/enrolled-layout-11-2024',
 'registration-layout-2022': '/sos/elections-voting/voter-data/enrolled-layout-11-2022',
}

def capture(source_id, original_url, request_url=None):
    request_url = request_url or original_url
    when = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with requests.get(request_url, timeout=30, stream=True) as r:
        chunks=[]; n=0
        for chunk in r.iter_content(65536):
            n+=len(chunk)
            if n>38*1024*1024: raise ValueError('source exceeds bounded 38 MiB request')
            chunks.append(chunk)
        body=b''.join(chunks)
        ext = '.xlsx' if body[:2]==b'PK' else '.pdf' if body[:4]==b'%PDF' else '.txt' if '.txt' in original_url else '.html'
        saved=Path('raw')/(source_id+ext+'.gz')
        (ROOT/saved).write_bytes(gzip.compress(body,mtime=0))
        return dict(source_id=source_id,original_url=original_url,request_url=request_url,
                    final_url=r.url,retrieved_utc=when,http_status=r.status_code,
                    redirects=[dict(url=x.url,status=x.status_code,headers=dict(x.headers)) for x in r.history],
                    headers=dict(r.headers),archive_capture=None,original_bytes=len(body),
                    original_sha256=hashlib.sha256(body).hexdigest(),saved_path=str(saved),
                    saved_sha256=hashlib.sha256((ROOT/saved).read_bytes()).hexdigest())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--only',nargs='+');a=p.parse_args()
    path=ROOT/'manifest.json'; old=json.loads(path.read_text()) if path.exists() else []
    byid={x['source_id']:x for x in old}
    targets={k:(BASE+v,(BASE+v).replace('https://www.','https://www3.')) for k,v in FILES.items()}
    targets.update({x['source_id']:(x['original_url'],x['request_url']) for x in old})
    for name, (original,request_url) in targets.items():
        if a.only and name not in a.only: continue
        # www3 is an official live host. Preserve the original linked www URL;
        # this is a host alternative, not an archived publication.
        previous=byid.get(name)
        if previous:
            oldbytes=(ROOT/previous['saved_path']).read_bytes()
        item=capture(name,original,request_url)
        if previous:item=previous|item
        if previous and item['original_sha256']!=previous['original_sha256']:
            historic=Path('raw/revisions')/(name+'-'+previous['original_sha256']+'.gz')
            (ROOT/historic).parent.mkdir(exist_ok=True)
            (ROOT/historic).write_bytes(oldbytes)
            item['previous_versions']=previous.get('previous_versions',[])+[previous|{'saved_path':str(historic)}]
        byid[name]=item; print(name,item['http_status'],item['original_bytes'])
        path.write_text(json.dumps(list(byid.values()),indent=2)+'\n')
