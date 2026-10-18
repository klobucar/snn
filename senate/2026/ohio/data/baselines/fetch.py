#!/usr/bin/env python3
"""Fetch public primary evidence; retain exact decoded response bytes and HTTP metadata."""
import datetime,gzip,hashlib,json,pathlib,sys,requests
ROOT=pathlib.Path(__file__).resolve().parent

def fetch(name,url):
 p=ROOT/'raw'/name
 t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  r=requests.get(url,timeout=90,headers={'User-Agent':'OhioHistoricalResearch/1.0 (public certified election research)'})
  b=r.content
  if name.endswith('.gz'): p.write_bytes(gzip.compress(b,mtime=0))
  else: p.write_bytes(b)
  meta={'url':url,'retrieved_utc':t,'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':r.status_code,'final_url':r.url,'headers':dict(r.headers),'redirects':[{'url':x.url,'status':x.status_code,'headers':dict(x.headers)} for x in r.history], 'decoded_bytes':len(b),'sha256_decoded':hashlib.sha256(b).hexdigest(),'sha256_stored':hashlib.sha256(p.read_bytes()).hexdigest(),'stored_path':str(p.relative_to(ROOT))}
 except Exception as e: meta={'url':url,'retrieved_utc':t,'error':str(e)}
 p.with_name(p.name+'.meta.json').write_text(json.dumps(meta,indent=2)+'\n')
 print(name,meta.get('status'),meta.get('decoded_bytes'),meta.get('final_url',meta.get('error')))
 return meta
if __name__=='__main__':fetch(sys.argv[1],sys.argv[2])
