#!/usr/bin/env python3
"""Replay exact public URLs into a NEW snapshot directory; never overwrite retained evidence."""
from pathlib import Path
import argparse,datetime,gzip,hashlib,json,urllib.error,urllib.request
R=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args();out=Path(args.output).resolve();assert out!=R and R not in out.parents,'choose a separate output snapshot';out.mkdir(parents=True,exist_ok=False)
for i,m in enumerate(json.loads((R/'source-ledger.json').read_text())):
 url=m['requested_url'];stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  try:r=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'OhioElectionMapsResearch/1.0'}),timeout=75)
  except urllib.error.HTTPError as e:r=e
  with r:b=r.read();status=r.status;headers=dict(r.headers);final=r.url
  d=dict(url=url,final_url=final,retrieved_utc=stamp,status=status,headers=headers)
 except Exception as e:b=b'';d=dict(url=url,retrieved_utc=stamp,status=None,error=str(e))
 d.update(bytes=len(b),sha256=hashlib.sha256(b).hexdigest());name=f'{i:04d}';packed=gzip.compress(b,mtime=0);(out/(name+'.gz')).write_bytes(packed);d['stored_sha256']=hashlib.sha256(packed).hexdigest();(out/(name+'.json')).write_text(json.dumps(d,indent=2)+'\n');print(i,d['status'],url,flush=True)
