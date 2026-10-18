#!/usr/bin/env python3
"""Verify retained newsroom evidence and observed election identities offline."""
from pathlib import Path
import gzip,hashlib,json
ROOT=Path(__file__).resolve().parent
rows=json.loads((ROOT/'manifest.json').read_text())
for r in rows:
 if 'asset' not in r:continue
 b=(ROOT/r['asset']).read_bytes();assert hashlib.sha256(b).hexdigest()==r['stored_sha256'],r['id']
 raw=gzip.decompress(b);assert hashlib.sha256(raw).hexdigest()==r['raw_sha256'],r['id']
def raw(name):
 r=next(x for x in rows if x['id']==name)
 return gzip.decompress((ROOT/r['asset']).read_bytes()).decode(errors='replace')
s=raw('ans-results')
assert '"selectedElection":{"id":"2472","isActive":false,"name":"2026 Alaska Primary"' in s
assert '"displayTestData":true' in s
assert '8:45 p.m. and 9 p.m.' in raw('akpublic-general-2026')
assert 'Nov. 18' in raw('akpublic-general-2026')
assert 'after 9' in raw('division-calendar')
assert next(r for r in rows if r['id']=='nyt-elections')['status']==403
result={'status':'pass','retained_assets':sum('asset' in r for r in rows),'ans_selected_election':'2026 Alaska Primary','ans_display_test_data':True,'nyt_access_status':403,'november_feed_established':False}
(ROOT/'inspection.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
