#!/usr/bin/env python3
"""Verify retained evidence and extract source state without relying on index text."""
import gzip,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
rows=json.loads((ROOT/'manifest.json').read_text())
for r in rows:
 if 'asset' not in r: continue
 b=(ROOT/r['asset']).read_bytes();assert hashlib.sha256(b).hexdigest()==r['stored_sha256'],r['id']
 raw=gzip.decompress(b);assert hashlib.sha256(raw).hexdigest()==r['raw_sha256'],r['id']

def raw(name):
 r=next(x for x in rows if x['id']==name);return gzip.decompress((ROOT/r['asset']).read_bytes()).decode(errors='replace')
wr=json.loads(raw('wral-2024-data'))
assert len(wr['races'])==1216
assert wr['lastModified']=='Tue, 03 Dec 2024 18:32:58 GMT'
assert 'disable-refresh' in raw('wral-results-linked')
assert '2026 Primary Election' in raw('wway-2026-embed')
assert '3/4/2026 8:45:23 AM' in raw('wway-2026-embed')
assert json.loads(raw('wlos-playlist'))['ElectionPlaylist']['contest']==[]
assert '30000' in raw('wlos-embed')
obs={'wral_races':len(wr['races']),'wral_lastModified':wr['lastModified'],'wlos_contests':0,'sources':[]}
for name in ['wbtv-results','witn-results','wect-results']:
 s=raw(name)
 assert '"displayTestData":true' in s,name
 # These are explicit source-state fields, not assumptions about displayed candidate totals.
 selections=re.findall(r'"selectedElection":(\{.*?\}),"hasRecentUpdates"',s)
 obs['sources'].append({'id':name,'display_test_data':True,'selected_election_names':sorted(set(re.findall(r'"selectedElection":\{"id"[^}]*?"name":"([^"]*)"',s))),'null_selection':'"selectedElection":{"id":null}' in s})
obs['verified_assets']=sum('asset' in r for r in rows)
(ROOT/'inspection.json').write_text(json.dumps(obs,indent=2)+'\n')
print(json.dumps(obs,indent=2))
