#!/usr/bin/env python3
"""Explicit source-supported URLs only; retain every response including failures."""
import requests,gzip,hashlib,datetime,json,pathlib,argparse
P=pathlib.Path(__file__).resolve().parent

def fetch(name,url):
 t=datetime.datetime.now(datetime.timezone.utc).isoformat();r=requests.get(url,timeout=45);b=r.content
 stored=gzip.compress(b,mtime=0);p=P/'raw'/f'{name}.body.gz';p.write_bytes(stored)
 m=dict(id=name,requested_url=url,final_url=r.url,retrieved_at_utc=t,status=r.status_code,headers=dict(r.headers),original_bytes=len(b),original_sha256=hashlib.sha256(b).hexdigest(),stored_path=str(p.relative_to(P)),stored_bytes=len(stored),stored_sha256=hashlib.sha256(stored).hexdigest(),storage='lossless gzip of HTTP-decoded response')
 (P/'raw'/f'{name}.meta.json').write_text(json.dumps(m,indent=2)+'\n');print(name,r.status_code,len(b),m['original_sha256']);return b
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('id');a.add_argument('url');args=a.parse_args();fetch(args.id,args.url)
