#!/usr/bin/env python3
"""Copy coordinator-verified county server render and exact provenance into assigned package only."""
from pathlib import Path
import gzip,hashlib,json,shutil
R=Path(__file__).resolve().parent;S=R.parent/'data/map-review';O=R/'evidence/coordinator-review';O.mkdir(parents=True,exist_ok=True)
entries=json.loads((S/'manifest.json').read_text())
for id in ['tuscarawas-official-render','tuscarawas-minimal-geometry','tuscarawas-server']:
 m=next(m for m in entries if m['id']==id);p=S/m['asset'];b=gzip.decompress(p.read_bytes());assert hashlib.sha256(b).hexdigest()==m['raw_sha256'];assert hashlib.sha256(p.read_bytes()).hexdigest()==m['stored_sha256'];q=O/(id+'.gz');shutil.copyfile(p,q)
 d=dict(key='coordinator-review/'+id,requested_url=m['url'],final_url=m['final_url'],retrieved_utc=m['retrieved_at_utc'],status=m['status'],headers=m['headers'],bytes=m['bytes'],sha256=m['raw_sha256'],stored_sha256=m['stored_sha256'],stored_path=str(q.relative_to(R)),imported_from='read-only ../data/map-review/manifest.json; no new retrieval time invented')
 (O/(id+'.meta.json')).write_text(json.dumps(d,indent=2)+'\n');(O/(id+'-original-record.json')).write_text(json.dumps(m,indent=2)+'\n')
 if id=='tuscarawas-official-render':
  png=S/(id+'.png');assert png.read_bytes()==b;shutil.copyfile(png,O/(id+'.png'))
shutil.copyfile(S/'tuscarawas-render-request.json',O/'tuscarawas-render-request.json')
print('verified county server render imported with original URL/time/headers/hash')
