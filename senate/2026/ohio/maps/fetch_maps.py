#!/usr/bin/env python3
"""Retain exact public responses with gzip, HTTP headers and content hashes. Writes only maps/."""
import concurrent.futures,datetime,gzip,hashlib,json,re,subprocess,threading,time,urllib.parse
from html.parser import HTMLParser
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parent
LOCK=threading.Lock()
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.href=None;self.label=[]
 def handle_starttag(self,tag,attrs):
  if tag=='a':self.href=dict(attrs).get('href');self.label=[]
 def handle_data(self,data):
  if self.href:self.label.append(data)
 def handle_endtag(self,tag):
  if tag=='a' and self.href:self.links.append((self.href,' '.join(self.label).strip()));self.href=None

def fetch(key,url,raw=False):
 out=ROOT/'evidence'/key;out.parent.mkdir(parents=True,exist_ok=True)
 mp=out.with_suffix(out.suffix+'.meta.json');bp=out.with_suffix(out.suffix+('.bin' if raw else '.gz'))
 if mp.exists():return json.loads(mp.read_text()),bp.read_bytes() if raw else gzip.decompress(bp.read_bytes())
 now=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  r=requests.get(url,timeout=75,headers={'User-Agent':'OhioElectionMapsResearch/1.0 (public map archival)'})
  b=r.content;m={'key':key,'requested_url':url,'final_url':r.url,'retrieved_utc':now,'status':r.status_code,'headers':dict(r.headers),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'stored_path':str(bp.relative_to(ROOT))}
 except Exception as e:b=b'';m={'key':key,'requested_url':url,'retrieved_utc':now,'status':None,'error':str(e),'bytes':0,'sha256':hashlib.sha256(b).hexdigest(),'stored_path':str(bp.relative_to(ROOT))}
 bp.write_bytes(b if raw else gzip.compress(b,mtime=0));m['stored_sha256']=hashlib.sha256(bp.read_bytes()).hexdigest();mp.write_text(json.dumps(m,indent=2)+'\n');return m,b

def links(b,url):
 p=Links();p.feed(b.decode('utf-8','replace'));return [(urllib.parse.urljoin(url,h),t) for h,t in p.links if not h.startswith(('mailto:','tel:','javascript:','#'))]

def main():
 rows=list(__import__('csv').DictReader((ROOT.parent/'data/county-turnout.csv').open()))
 def work(r):
  name=r['county'];key=name.lower().replace(' ','-');url='https://www.boe.ohio.gov/'+key+'/'
  m,b=fetch('landing/'+key,url)
  found=[(u,t) for u,t in links(b,m.get('final_url',url)) if re.search('map|GIS|district|precinct',t+' '+u,re.I)]
  return {'county':name,'county_fips':r['county_fips'],'priority':r['in_minimum80']=='1','landing_url':url,'status':m['status'],'links':list(dict.fromkeys(found))}
 with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:out=list(ex.map(work,rows))
 (ROOT/'initial-inventory.json').write_text(json.dumps(out,indent=2)+'\n')
 for r in out[:32]:print(r['county'],r['status'],r['links'][:14],flush=True)
if __name__=='__main__':main()
