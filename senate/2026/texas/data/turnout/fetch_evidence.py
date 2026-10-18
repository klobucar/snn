#!/usr/bin/env python3
"""Retain exact response payloads, headers and UTC for requested public evidence."""
import argparse,datetime,gzip,hashlib,json,pathlib,requests
ROOT=pathlib.Path(__file__).resolve().parent

def fetch(key,url):
    start=datetime.datetime.now(datetime.timezone.utc).isoformat()
    r=requests.get(url,timeout=90,headers={'User-Agent':'Texas-election-research/1.0 (public historical returns)'})
    body=r.content; stored=gzip.compress(body,mtime=0)
    path=ROOT/'raw'/f'{key}.body.gz'; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(stored)
    meta={'id':key,'requested_url':url,'final_url':r.url,'retrieved_at_utc':start,'status':r.status_code,'headers':dict(r.headers),'original_bytes':len(body),'original_sha256':hashlib.sha256(body).hexdigest(),'stored_path':str(path.relative_to(ROOT)),'stored_bytes':len(stored),'stored_sha256':hashlib.sha256(stored).hexdigest(),'storage':'gzip lossless HTTP decoded payload; gzip Content-Encoding decoded by requests'}
    if len(stored)>=40000000:
        parts=[]
        for i,start in enumerate(range(0,len(stored),32000000),1):
            piece=stored[start:start+32000000];part=path.with_name(path.name+f'.part{i:03d}');part.write_bytes(piece);parts.append({'path':str(part.relative_to(ROOT)),'bytes':len(piece),'sha256':hashlib.sha256(piece).hexdigest()})
        meta['stored_parts']=parts;meta.pop('stored_path',None);meta['storage']='lossless gzip byte-split into ordered <40000000-byte parts; concatenate before decompressing';path.unlink()
    (ROOT/'raw'/f'{key}.meta.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(key,r.status_code,len(body),r.url,flush=True)
    return body,meta
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('key');p.add_argument('url');a=p.parse_args();fetch(a.key,a.url)
