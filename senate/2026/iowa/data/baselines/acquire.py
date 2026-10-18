#!/usr/bin/env python3
"""Snapshot read-only source references; verify original bytes; refresh key HTTP chains.
No duplicated statewide originals when refreshed entity hashes match retained bytes.
"""
import datetime, json, requests
from pathlib import Path
from common import ROOT, TURNOUT, raw, sha, dump, gzwrite
def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--reuse-only',action='store_true',help='verify and snapshot final retained references, without any network request');args=parser.parse_args()
    originals=json.loads((TURNOUT/'source-manifest.json').read_text())
    refs=[]
    for r in originals:
        q=dict(r);q['peer_manifest']='../turnout/source-manifest.json'
        if r.get('path'):
            q['path']=str(Path('../turnout')/r['path']);raw(q)
        refs.append(q)
    dump('sources.json',refs)
    if args.reuse_only:
        print('Verified and pinned',len(refs),'final read-only source references; no network request')
        return
    evidence=[]
    for r in refs:
        if not (r['id'].endswith('canvass') or r['id'].endswith('precinct-index') or r['id']=='sos-results-index' or r['id']=='sos-2024-precinct-app'):continue
        response=requests.get(r['url'],timeout=60)
        b=response.content;item={'id':r['id'],'requested_url':r['url'],'retrieval_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':response.status_code,'final_url':response.url,'headers':dict(response.headers),'redirects':[{'url':h.url,'status':h.status_code,'headers':dict(h.headers)} for h in response.history],'original_sha256':sha(b),'original_bytes':len(b),'same_as_retained_original':sha(b)==r.get('original_sha256')}
        if not item['same_as_retained_original']:
            path='http-refresh/'+r['id']+'.gz';gzwrite(path,b);item['path']=path
        evidence.append(item)
    dump('http-refresh.json',evidence)
    print('Verified',len(refs),'source references;',len(evidence),'fresh request chains')
if __name__=='__main__':main()
