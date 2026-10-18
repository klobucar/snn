#!/usr/bin/env python3
"""Bounded, auditable public-source acquisitions. No live election collector."""
import argparse, datetime, gzip, hashlib, json, pathlib, sys, fcntl, os
import requests
ROOT = pathlib.Path(__file__).resolve().parent
MANIFEST = ROOT / 'acquisitions.json'
CAP = 39_000_000
def digest(b): return hashlib.sha256(b).hexdigest()
def fetch(key, url, kind='text', note='', refresh=False, verify=True):
    records = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    if key in records and not refresh:
        p=ROOT/records[key]['path']
        return gzip.decompress(p.read_bytes()) if str(p).endswith('.gz') else p.read_bytes()
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        r=requests.get(url,timeout=(20,90),stream=True,verify=verify,headers={'User-Agent':'MaineBoundaryResearch/1.0 (public research; bounded requests)'})
    except requests.RequestException as e:
        p=ROOT/'network-errors.json';errors=json.loads(p.read_text()) if p.exists() else []
        errors.append({'key':key,'url':url,'retrieved_utc':now,'error':str(e),'tls_verify':verify,'note':note})
        p.write_text(json.dumps(errors,indent=2)+'\n');raise
    chunks=[]; size=0
    for c in r.iter_content(65536):
        size+=len(c)
        if size>150_000_000: raise ValueError('Uncompressed response cap exceeded')
        chunks.append(c)
    body=b''.join(chunks)
    stored=gzip.compress(body,mtime=0) if kind=='text' else body
    if len(stored)>=CAP: raise ValueError('Retained object exceeds cap; split source before acquisition')
    ext={'text':'.gz','pdf':'.pdf','zip':'.zip','image':'.png'}[kind]
    path=ROOT/'raw'/(key+ext);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(stored)
    record={'url':url,'final_url':r.url,'retrieved_utc':now,'status':r.status_code,'requested_kind':kind,
      'headers':dict(r.headers),'redirects':[{'url':x.url,'status':x.status_code,'headers':dict(x.headers)} for x in r.history],
      'path':str(path.relative_to(ROOT)),'original_bytes':len(body),'stored_bytes':len(stored),
      'original_sha256':digest(body),'stored_sha256':digest(stored),'storage':'lossless gzip of response entity bytes' if kind=='text' else 'unchanged response entity bytes',
      'note':note,'tls_verify':verify,'body_prefix':body[:100].decode('utf8','replace') if kind=='text' or not body.startswith((b'%PDF',b'PK')) else ''}
    with (ROOT/'.acquisitions.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        records=json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
        records[key]=record
        temp=MANIFEST.with_suffix('.tmp');temp.write_text(json.dumps(records,indent=2)+'\n');os.replace(temp,MANIFEST)
    print(key,r.status_code,len(body),flush=True)
    return body
def load(key):
    r=json.loads(MANIFEST.read_text())[key];p=ROOT/r['path']
    return gzip.decompress(p.read_bytes()) if str(p).endswith('.gz') else p.read_bytes()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('key');p.add_argument('url');p.add_argument('--kind',default='text');p.add_argument('--note',default='');p.add_argument('--refresh',action='store_true');a=p.parse_args()
    fetch(a.key,a.url,a.kind,a.note,a.refresh)
