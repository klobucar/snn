#!/usr/bin/env python3
"""Bounded public source acquisition. Writes only maps/. No source rewriting."""
import concurrent.futures, datetime, gzip, hashlib, json, pathlib, re, sys
from html.parser import HTMLParser
from urllib.parse import urljoin, unquote
import requests

ROOT = pathlib.Path(__file__).resolve().parent
LIMIT = 40_000_000
def sha(b): return hashlib.sha256(b).hexdigest()
def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False)+'\n')
def fetch(key, url, parent=None, kind='evidence', **extra):
    """Retain decoded HTTP entity and full observed response/redirect metadata."""
    meta = ROOT/'raw'/f'{key}.meta.json'
    if meta.exists(): return json.loads(meta.read_text())
    meta.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    m = dict(source_id=key, requested_url=url, parent_authority_url=parent,
             kind=kind, retrieval_utc=now, **extra)
    try:
        r=requests.get(url, timeout=(20,90), headers={'User-Agent':'Iowa-public-map-research/1.0'}, stream=True)
        # All known objects are small. Bounded streaming avoids unbounded buffering.
        chunks=[]; n=0
        for c in r.iter_content(1024*1024):
            n+=len(c)
            if n>160_000_000: raise ValueError('response exceeds acquisition bound; no partial payload accepted')
            chunks.append(c)
        b=b''.join(chunks)
        ext='.zip' if b[:2]==b'PK' else '.pdf' if b[:5]==b'%PDF-' else '.gz'
        stored=gzip.compress(b,mtime=0) if ext=='.gz' else b
        path=ROOT/'raw'/f'{key}{ext}'
        m.update(final_url=r.url,status=r.status_code,reason=r.reason,
                 headers=dict(r.headers),request_headers=dict(r.request.headers),
                 redirects=[dict(status=x.status_code,url=x.url,headers=dict(x.headers)) for x in r.history],
                 entity_bytes=len(b),entity_sha256=sha(b),transport_decoding='requests HTTP content decoding; no other modification')
        if len(stored)>=LIMIT:
            # Exact byte-order split, no truncation. Reconstruction concatenates listed parts.
            parts=[]
            for i in range(0,len(stored),39_000_000):
                part=path.with_name(path.name+f'.part{i//39_000_000:03d}')
                piece=stored[i:i+39_000_000];part.write_bytes(piece)
                parts.append(dict(path=str(part.relative_to(ROOT)),bytes=len(piece),sha256=sha(piece)))
            m.update(parts=parts,stored_encoding='ordered byte concatenation; '+('gzip' if ext=='.gz' else 'identity'),stored_sha256=sha(stored),stored_bytes=len(stored))
        else:
            path.write_bytes(stored)
            m.update(path=str(path.relative_to(ROOT)),stored_encoding='gzip' if ext=='.gz' else 'identity',stored_bytes=len(stored),stored_sha256=sha(stored))
    except Exception as e: m.update(error=type(e).__name__+': '+str(e),status=None)
    write_json(meta,m)
    return m
def body(m):
    b=(ROOT/m['path']).read_bytes() if 'path' in m else b''.join((ROOT/p['path']).read_bytes() for p in m['parts'])
    return gzip.decompress(b) if 'gzip' in m['stored_encoding'] else b
class Links(HTMLParser):
    def __init__(self): super().__init__();self.links=[]
    def handle_starttag(self,t,a):
        d=dict(a)
        if t=='a' and d.get('href'):self.links.append(d['href'])
def links(m):
    p=Links();p.feed(body(m).decode('utf-8','replace'))
    return list(dict.fromkeys(urljoin(m['final_url'],x) for x in p.links))
def slug(s): return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-')
def main():
    sources=[('sos-shapefile-hub','https://sos.iowa.gov/precinct-and-district-shapefiles'),
             ('sos-county-index','https://sos.iowa.gov/shapefiles-county-precincts'),
             ('sos-city-index','https://sos.iowa.gov/shapefiles-city'),
             ('sos-city-current-index','https://sos.iowa.gov/shapefiles-city-precincts'),
             ('sos-county-directory','https://sos.iowa.gov/shapefiles-county'),
             ('sos-statewide-index','https://sos.iowa.gov/shapefiles-statewide'),
             ('sos-reprecincting','https://sos.iowa.gov/redistricting-reprecincting')]
    pages=[fetch(k,u,kind='authority-index') for k,u in sources]
    targets=[]
    for p in pages:
        if p['source_id'] not in ('sos-county-index','sos-city-index','sos-city-current-index','sos-statewide-index'):continue
        for u in links(p):
            if unquote(u).lower().endswith('.zip'):
                name=unquote(u.rsplit('/',1)[-1]); key=slug(p['source_id'].replace('-index','')+'-'+name[:-4])
                targets.append((key,u,p['final_url'],name))
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(lambda t:fetch(t[0],t[1],t[2],kind='native-shapefile-archive',native_link_filename=t[3],approval_status='unestablished; publication/edit date is not legal adoption'),targets))
    write_json(ROOT/'source-manifest.json',dict(schema_version=1,records=[json.loads(p.read_text()) for p in sorted((ROOT/'raw').glob('*.meta.json'))]))
    print(json.dumps(dict(records=len(pages+results),archives=len(results),statuses={str(s):sum(r.get('status')==s for r in results) for s in set(r.get('status') for r in results)})))
if __name__=='__main__': main()
