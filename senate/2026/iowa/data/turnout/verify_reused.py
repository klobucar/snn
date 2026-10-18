#!/usr/bin/env python3
"""Refresh metadata for reused originals without duplicating identical payloads."""
import gzip,json
from pathlib import Path
import acquire as a
import requests

def main():
    out=[]
    for r in a.load():
        if not r.get('peer_manifest'):continue
        when=a.stamp()
        try:
            q=requests.get(r['url'],timeout=90,headers={'User-Agent':'Iowa-election-research/1.0 (public historical downloads)'})
            data=q.content;digest=a.sha(data);same=digest==r['original_sha256']
            v=dict(source_id=r['id'],url=r['url'],retrieval_utc=when,status=q.status_code,final_url=q.url,redirects=[dict(url=h.url,status=h.status_code,headers=dict(h.headers)) for h in q.history],headers=dict(q.headers),original_bytes=len(data),original_sha256=digest,matches_pinned_original=same)
            if same:v['body_reference']=r['path']
            else:
                p=Path('originals')/(r['id']+'-verification-response.gz');stored=gzip.compress(data,mtime=0);assert len(stored)<40000000;(a.ROOT/p).write_bytes(stored);v.update(body_reference=str(p),stored_sha256=a.sha(stored),stored_bytes=len(stored),scope='fresh response differs from pinned original; never replaces baseline evidence')
            out.append(v);print(r['id'],q.status_code,same,flush=True)
        except Exception as e:out.append(dict(source_id=r['id'],url=r['url'],retrieval_utc=when,error=str(e)))
        (a.ROOT/'reused-request-verification.json').write_text(json.dumps(out,indent=2)+'\n')
if __name__=='__main__':main()
