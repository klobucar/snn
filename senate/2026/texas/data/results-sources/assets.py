#!/usr/bin/env python3
"""Hash only owned files. No Git operation or shared-file mutation."""
import hashlib,json
from fetch import ROOT
TX=ROOT.parents[1]
def build():
    files=[TX/'official-results.md',TX/'data/official-results-sources.csv']+[p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='asset-manifest.json']
    out=[]
    for p in sorted(files):
        b=p.read_bytes();assert len(b)<40000000,str(p)
        out.append(dict(path=str(p.relative_to(TX)),bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
    x=dict(ownership='official-results.md; data/official-results-sources.csv; data/results-sources/** only',self_excluded=True,strict_asset_limit=40000000,assets=out)
    (ROOT/'asset-manifest.json').write_text(json.dumps(x,indent=2)+'\n');print(json.dumps(dict(assets=len(out),bytes=sum(a['bytes'] for a in out),largest=max(a['bytes'] for a in out))))
if __name__=='__main__':build()
