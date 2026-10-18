#!/usr/bin/env python3
"""Public GET evidence recorder. Network only; offline validation uses stdlib.

Usage: python3 fetch.py ID URL [PARENT_ID] [PURPOSE]
Entity bytes are requests' transfer/content-decoded response.content, retained
without text transcoding. Headers separately record upstream content encoding.
Large lossless gzip streams are split at 32 MB, never truncated.
"""
import datetime, gzip, hashlib, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent
def sha(b): return hashlib.sha256(b).hexdigest()
def fetch(sid, url, parent=None, purpose=None):
    import requests
    meta_path=ROOT/'raw'/f'{sid}.json'
    if meta_path.exists(): return json.loads(meta_path.read_text())
    start=datetime.datetime.now(datetime.timezone.utc).isoformat()
    m=dict(id=sid,request_url=url,parent_id=parent,purpose=purpose,retrieval_started_utc=start,
           method='GET',request_headers={'User-Agent':'Mozilla/5.0 (public election research)'},
           body_scope='complete response entity; not a claim of complete election coverage')
    try:
        r=requests.get(url,headers=m['request_headers'],timeout=(15,50))
        b=r.content
        m.update(status=r.status_code,final_url=r.url,headers=dict(r.headers),
          redirects=[dict(status=h.status_code,url=h.url,headers=dict(h.headers)) for h in r.history],
          original_bytes=len(b),original_sha256=sha(b),body_complete=True,
          entity_definition='content/transfer-decoded response bytes, no character conversion')
        z=gzip.compress(b,mtime=0);m.update(stored_stream_bytes=len(z),stored_stream_sha256=sha(z))
        parts=[]
        for i in range(0,len(z),32000000):
            suffix='.body.gz' if len(z)<40000000 else f'.body.gz.part{i//32000000+1:03d}'
            p=ROOT/'raw'/(sid+suffix); chunk=z[i:i+32000000] if len(z)>=40000000 else z
            p.write_bytes(chunk);parts.append(dict(path=str(p.relative_to(ROOT)),bytes=len(chunk),sha256=sha(chunk)))
            if len(z)<40000000:break
        m['stored_parts']=parts
    except Exception as e:
        m.update(status=None,final_url=None,body_complete=False,error=type(e).__name__+': '+str(e))
    m['retrieval_finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    meta_path.write_text(json.dumps(m,indent=2)+'\n')
    return m
def read(sid):
    m=json.loads((ROOT/'raw'/f'{sid}.json').read_text())
    return gzip.decompress(b''.join((ROOT/p['path']).read_bytes() for p in m['stored_parts']))
if __name__=='__main__':
    m=fetch(*sys.argv[1:]); print(json.dumps({k:m.get(k) for k in ['id','status','final_url','original_bytes','error']}))
