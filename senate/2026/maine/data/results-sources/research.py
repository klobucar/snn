#!/usr/bin/env python3
"""Bounded, public-only evidence fetcher. No credentials, hidden endpoints or Git.
Original HTTP entity bytes retained losslessly; headers/redirects and derived text
are separate. All paths are within this assignment. python3 research.py URL ...
"""
import concurrent.futures,csv,datetime,gzip,hashlib,html,json,re,sys,time,urllib.error,urllib.parse,urllib.request
from pathlib import Path
from html.parser import HTMLParser
ROOT=Path(__file__).resolve().parent
MAX=39_000_000
class Parser(HTMLParser):
 def __init__(self,base):super().__init__();self.base=base;self.links=[];self.text=[];self.a=None;self.skip=0;self.scripts=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='base' and a.get('href'):self.base=urllib.parse.urljoin(self.base,a['href'])
  if tag in ('style','script'):self.skip+=1
  if tag=='script' and a.get('src'):self.scripts.append(urllib.parse.urljoin(self.base,a['src']))
  if tag=='a' and a.get('href'):self.a=[urllib.parse.urljoin(self.base,a['href']),[]]
  if tag in ('p','div','br','h1','h2','h3','tr','li'):self.text.append('\n')
 def handle_endtag(self,tag):
  if tag in ('style','script'):self.skip=max(0,self.skip-1)
  if tag=='a' and self.a:self.links.append({'url':self.a[0],'text':' '.join(self.a[1]).strip()});self.a=None
 def handle_data(self,data):
  if self.a:self.a[1].append(data.strip())
  if not self.skip:self.text.append(data)
def digest(b):return hashlib.sha256(b).hexdigest()
class Redirects(urllib.request.HTTPRedirectHandler):
 def __init__(self):self.history=[]
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  self.history.append({'url':req.full_url,'status':code,'location':newurl,'headers':list(headers.items())})
  return super().redirect_request(req,fp,code,msg,headers,newurl)
def fetch(url,tag=None,limit=MAX,publisher_url=None,headers=None):
 id=tag or digest(url.encode())[:20]
 dest=ROOT/'requests';dest.mkdir(exist_ok=True)
 meta={'id':id,'publisher_url':publisher_url or url,'request_url':url,'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'requested_headers':headers or {},'max_entity_bytes':limit,'redirects':[]}
 red=Redirects();op=urllib.request.build_opener(red)
 req=urllib.request.Request(url,headers={'User-Agent':'Maine-public-election-research/1.0','Accept-Encoding':'identity',**(headers or {})})
 body=b''
 try:
  try:r=op.open(req,timeout=25)
  except urllib.error.HTTPError as e:r=e
  meta.update(status=r.code,final_url=r.url,headers=list(r.headers.items()))
  body=r.read(limit+1);meta['complete']=len(body)<=limit
  if not meta['complete']:body=body[:limit]
  r.close()
 except Exception as e:meta.update(status=None,error=repr(e),complete=False)
 meta['redirects']=red.history;meta['entity_bytes_retained']=len(body);meta['entity_sha256']=digest(body)
 blob=gzip.compress(body,mtime=0);p=ROOT/'objects'/f'{digest(body)}.gz';p.parent.mkdir(exist_ok=True)
 if not p.exists():p.write_bytes(blob)
 meta['body_path']=str(p.relative_to(ROOT));meta['saved_sha256']=digest(p.read_bytes());meta['saved_bytes']=p.stat().st_size
 target=dest/f'{id}.json'
 if target.exists():
  previous=json.loads(target.read_text())
  obs=ROOT/'observations'/id;obs.mkdir(parents=True,exist_ok=True)
  stamp=re.sub(r'[^0-9]','',meta['retrieved_utc'])
  (obs/f'{stamp}.json').write_text(json.dumps(meta,indent=2)+'\n')
  oldstamp=re.sub(r'[^0-9]','',previous['retrieved_utc'])
  (obs/f'{oldstamp}.json').write_text(json.dumps(previous,indent=2)+'\n')
  if previous['entity_sha256']==meta['entity_sha256']:return previous
 target.write_text(json.dumps(meta,indent=2)+'\n')
 if 'html' in dict(meta.get('headers',[])).get('Content-Type','').lower() or b'<html' in body[:3000].lower() or b'<!doctype html' in body[:3000].lower():
  parser=Parser(meta.get('final_url',url))
  try:parser.feed(body.decode('utf-8',errors='replace'))
  except Exception:pass
  (dest/f'{id}.links.json').write_text(json.dumps({'links':parser.links,'scripts':parser.scripts},indent=2)+'\n')
  (dest/f'{id}.txt').write_text(re.sub(r'[ \t]+',' ',''.join(parser.text)))
 return meta
if __name__=='__main__':
 for u in sys.argv[1:]:
  m=fetch(u);print(m['id'],m.get('status'),m['entity_bytes_retained'],m.get('error',''))
