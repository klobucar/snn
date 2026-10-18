#!/usr/bin/env python3
"""Bounded original-byte acquisition. No geographic transformations here.
Use with /tmp/tx-maps-venv/bin/python; dependencies listed in SCHEMA.md.
"""
import argparse, datetime, gzip, hashlib, json, re
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
PART = 32_000_000
CAP = 600_000_000

def sha(b): return hashlib.sha256(b).hexdigest()
def save_json(p, d): p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(d, indent=2, ensure_ascii=False)+'\n')
def fetch(key, url, parent=None, suffix=None, refresh=False):
    meta = ROOT/'sources'/f'{key}.json'
    if meta.exists() and not refresh: return json.loads(meta.read_text())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    d = dict(id=key, requested_url=url, parent_source_url=parent, retrieved_utc=now,
             byte_definition='HTTP response entity bytes after Content-Encoding decoding; requests Accept-Encoding: identity',
             cap_bytes=CAP)
    try:
        r = requests.get(url, timeout=(20,90), stream=True, headers={'User-Agent':'TexasElectionResearch/1.0 (public boundary archive)', 'Accept-Encoding':'identity'})
        d.update(status=r.status_code, final_url=r.url, headers=dict(r.headers), redirects=[dict(status=h.status_code,url=h.url,headers=dict(h.headers)) for h in r.history])
        chunks=[]; size=0
        for b in r.iter_content(1024*1024):
            size+=len(b)
            if size>CAP: raise ValueError('response exceeds bounded acquisition cap')
            chunks.append(b)
        b=b''.join(chunks)
        d.update(original_bytes=len(b),original_sha256=sha(b))
        # Reuse exact prior bytes by hash while retaining each route's HTTP metadata.
        for old in sorted((ROOT/'sources').glob('*.json')):
            prior=json.loads(old.read_text())
            if prior.get('original_sha256')==d['original_sha256'] and prior.get('stored_parts'):
                d.update(storage_encoding=prior['storage_encoding'],stored_parts=prior['stored_parts'],reused_exact_source=prior['id'],reconstruction=prior['reconstruction'])
                save_json(meta,d);return d
        suffix=suffix or ('.pdf' if b.startswith(b'%PDF') else '.zip' if b.startswith(b'PK\x03\x04') else '.body')
        folder=ROOT/'originals'; folder.mkdir(exist_ok=True)
        if len(b)<40_000_000:
            stored=b; encoding='identity'; ext=suffix
        else:
            # ZIP is already compressed; byte split keeps its exact original stream.
            stored=b if suffix=='.zip' else gzip.compress(b,mtime=0)
            encoding='identity' if suffix=='.zip' else 'gzip'
            ext=suffix+('' if encoding=='identity' else '.gz')
        paths=[]
        for i in range(0,len(stored),PART):
            name=f'{key}{ext}'+(f'.part{i//PART+1:03d}' if len(stored)>=40_000_000 else '')
            p=folder/name;p.write_bytes(stored[i:i+PART] if len(stored)>=40_000_000 else stored)
            paths.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p.read_bytes())))
            if len(stored)<40_000_000: break
        d.update(storage_encoding=encoding,stored_parts=paths,reconstruction='Concatenate stored_parts in listed order; gzip-decompress only if storage_encoding=gzip; verify original_bytes and original_sha256.')
    except Exception as e: d['error']=repr(e)
    save_json(meta,d);return d

def original(d):
    b=b''.join((ROOT/p['path']).read_bytes() for p in d['stored_parts'])
    b=gzip.decompress(b) if d['storage_encoding']=='gzip' else b
    assert len(b)==d['original_bytes'] and sha(b)==d['original_sha256']
    return b

def tlc():
    d=fetch('tlc-precinct-catalog','https://data.capitol.texas.gov/dataset/precincts')
    fetch('tlc-vtd-catalog','https://data.capitol.texas.gov/dataset/vtds')
    soup=BeautifulSoup(original(d),'html.parser')
    links=[urljoin(d['final_url'],a.get('href','')) for a in soup.select('a[href]')]
    for key,pattern in [('tlc-24g',r'/precincts24g\.zip'),('tlc-26p',r'/precincts26p\.zip'),('tlc-22g',r'/precincts22g\.zip'),('tlc-20g',r'/precincts20g_2020\.zip')]:
        urls=[u for u in links if re.search(pattern,u,re.I)]
        assert len(set(urls))==1,(key,urls)
        x=fetch(key,urls[0],d['requested_url'],'.zip');print(key,x.get('status'),x.get('original_bytes'),x.get('error'),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command');p.add_argument('url',nargs='?');p.add_argument('--parent');p.add_argument('--refresh',action='store_true');a=p.parse_args()
    if a.command=='tlc':tlc()
    else: print(json.dumps(fetch(a.command,a.url,a.parent,refresh=a.refresh),indent=2))
