#!/usr/bin/env python3
"""Retain public SOS download chains. No writes outside turnout/. Reuse peer bytes by hash."""
import concurrent.futures, gzip, hashlib, html, json, re, sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, quote, unquote, urlsplit, urlunsplit
import requests

ROOT = Path(__file__).resolve().parent
NEWS = ROOT.parent / 'news'
MANIFEST = ROOT / 'source-manifest.json'
def sha(b): return hashlib.sha256(b).hexdigest()
def stamp(): return datetime.now(timezone.utc).isoformat()
class Links(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]; self.current=None
    def handle_starttag(self, tag, attrs):
        if tag=='a': self.current=[dict(attrs).get('href',''),'']
    def handle_data(self, data):
        if self.current is not None: self.current[1]+=data
    def handle_endtag(self,tag):
        if tag=='a' and self.current is not None: self.links.append(tuple(self.current));self.current=None
def links(b):
    p=Links();p.feed(b.decode('utf-8',errors='replace'));return p.links
def load(): return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else []
def raw(r): return gzip.decompress((ROOT/r['path']).read_bytes())
def fetch(task):
    key,url,parent,label=task
    s=urlsplit(url); request_url=urlunsplit((s.scheme,s.netloc,quote(unquote(s.path),safe="/:'"),s.query,s.fragment))
    start=stamp()
    try:
        response=requests.get(request_url,timeout=90,headers={'User-Agent':'Iowa-election-research/1.0 (public historical downloads)'})
        b=response.content; stored=gzip.compress(b,mtime=0)
        if len(stored)>=40000000: raise ValueError('asset requires exact splitting, refusing oversize')
        path=Path('originals')/(key+'.gz');(ROOT/path).write_bytes(stored)
        return dict(id=key,url=url,request_url=request_url,parent_url=parent,link_label=label,retrieval_utc=start,completed_utc=stamp(),status=response.status_code,final_url=response.url,redirects=[dict(url=h.url,status=h.status_code,headers=dict(h.headers)) for h in response.history],headers=dict(response.headers),path=str(path),original_sha256=sha(b),original_bytes=len(b),stored_sha256=sha(stored),stored_bytes=len(stored),storage='gzip; original HTTP entity bytes after transport content-decoding',source_status='historical SOS linked export; document status interpreted separately')
    except Exception as e: return dict(id=key,url=url,parent_url=parent,link_label=label,retrieval_utc=start,error=str(e),status=None)
def main():
    ROOT.mkdir(exist_ok=True);(ROOT/'originals').mkdir(exist_ok=True)
    rows=load();ids={r['id'] for r in rows}
    # These are exact byte references, never copied large statewide originals.
    peer=json.loads((NEWS/'manifest.json').read_text())
    for r in peer:
        if (r['id'].startswith('sos-') and any(x in r['id'] for x in ['canvass','precinct-index','results-index','2024-precinct-app'])) or r['id']=='cass-results':
            if r['id'] in ids:continue
            b=gzip.decompress((NEWS/r['asset']).read_bytes()); assert sha(b)==r['raw_sha256']
            stored=(NEWS/r['asset']).read_bytes();assert sha(stored)==r['stored_sha256']
            rows.append(dict(id=r['id'],url=r['url'],parent_url='https://sos.iowa.gov/iowans/election-results-statistics' if r['id']!='sos-results-index' else None,link_label='See retained exact index HTML',retrieval_utc=r['retrieved_at_utc'],status=r['status'],final_url=r['final_url'],redirects=None,redirect_metadata_status='not recorded by original peer acquisition; final URL recorded',headers=r['headers'],path='../news/'+r['asset'],original_sha256=sha(b),stored_sha256=sha(stored),original_bytes=len(b),stored_bytes=len(stored),storage='read-only exact peer gzip reference',source_status='historical SOS publication',peer_manifest='../news/manifest.json',peer_id=r['id']))
    ids={r['id'] for r in rows}; index=next(r for r in rows if r['id']=='sos-results-index')
    tasks=[]
    for href,label in links(raw(index)):
        if any(f'/{y}/general/' in href for y in [2024,2022,2020]) and any(href.lower().endswith('/'+x) for x in ['turnout.pdf','countystats.pdf','statestats.pdf','precinctstats.pdf']):
            y=re.search(r'/(202[024])/general/',href).group(1);key='sos-'+y+'-'+href.split('/')[-1].lower().replace('.pdf','');tasks.append((key,urljoin(index['url'],href),index['url'],label.strip()))
    for year in [2022,2020]:
        ix=next(r for r in rows if r['id']==f'sos-{year}-precinct-index')
        for n,(href,label) in enumerate(links(raw(ix))):
            if f'/precinctresults/{year}general/' in href:
                name=unquote(href.split('/')[-1]).lower().replace(' ','-');key=f'sos-{year}-workbook-{n:03d}-{re.sub("[^a-z0-9.-]","",name)}';tasks.append((key,urljoin(ix['url'],href),ix['url'],label.strip()))
    tasks.append(('census-county-codes','https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt',None,'Census 2020 national county FIPS codes'))
    tasks.extend([
        ('cass-2024-local-canvass','https://www.casscountyia.gov/wp-content/uploads/2019/10/2024.11.05-General-Election-Results.pdf','https://www.casscountyia.gov/county-government/elections/','November 5 2024 General Election Canvass / Abstract / Results'),
        ('black-hawk-2022-filename-repair','https://sos.iowa.gov/elections/pdf/precinctresults/2022general/black%20hawk.xls','https://sos.iowa.gov/precinct-results-county-2022-general-0','Documented filename repair attempt: linked double space changed to single space, not actual link')
    ])
    todo=[t for t in tasks if t[0] not in ids]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for r in ex.map(fetch,todo):
            rows.append(r);MANIFEST.write_text(json.dumps(rows,indent=2)+'\n'); print(r['id'],r.get('status'),r.get('original_bytes'),flush=True)
    MANIFEST.write_text(json.dumps(rows,indent=2)+'\n')
if __name__=='__main__':main()
