#!/usr/bin/env python3
"""Build a hash-checked source ledger and owned-asset manifest, without network."""
from build import *
import os

def ledger():
 sources=[]
 own=sorted((P/'raw').glob('*.meta.json'))
 peer=[f for f in sorted((PEER/'raw').glob('*.meta.json')) if f.name.startswith(('oe2024-','oe-tx2020.','oe-tx2022.','medsl-senate-county.','medsl-readme.','sos2024-county-archive-','sos-2024-canvass-archive.','original-'))]
 for f in own+peer:
  m=json.loads(f.read_text());root=f.parent.parent;body=root/m['stored_path'] if 'stored_path' in m else None;parts=[dict(path=os.path.relpath(root/x['path'],P),bytes=x['bytes'],sha256=x['sha256']) for x in m.get('stored_parts',[])];b=body.read_bytes() if body else b''.join((P/x['path']).read_bytes() for x in parts);orig=gzip.decompress(b);assert sha(b)==m['stored_sha256'] and sha(orig)==m['original_sha256'],f
  sources.append(dict(source_id=m['id'],metadata_path=os.path.relpath(f,P),body_path=os.path.relpath(body,P) if body else None,stored_parts=parts,ownership='owned' if root==P else 'read-only shared turnout original',requested_url=m['requested_url'],final_url=m['final_url'],retrieved_at_utc=m['retrieved_at_utc'],http_status=m['status'],response_headers=m['headers'],original_bytes=len(orig),original_sha256=sha(orig),stored_bytes=len(b),stored_sha256=sha(b),storage=m['storage'],authority='primary SOS' if m['id'].startswith('sos') else 'primary county/vendor' if m['id'].startswith('original-') else 'primary legislature' if m['id'].startswith('journal') else 'secondary or discovery; see source-specific scope'))
 for m in json.loads((DATA/'news/manifest.json').read_text()):
  if m['id'] not in ['sos-results-app','sos-history-index','sos-historical-results','sos-turnout-controls','tlc-election-about','tlc-vtd-index','tlc-2024-general','tlc-2022-general','tlc-2024-senate-vtd','tlc-2024-president-vtd','tlc-2024-voterdata-vtd','tlc-2022-governor-vtd','tlc-2022-voterdata-vtd']:continue
  body=DATA/'news'/m['asset'];b=body.read_bytes();orig=gzip.decompress(b);assert sha(b)==m['stored_sha256'] and sha(orig)==m['raw_sha256']
  sources.append(dict(source_id=m['id'],metadata_path='../news/manifest.json',body_path=os.path.relpath(body,P) if body else None,stored_parts=parts,ownership='read-only coordinator original',requested_url=m['url'],final_url=m['final_url'],retrieved_at_utc=m['retrieved_at_utc'],http_status=m['status'],response_headers=m['headers'],original_bytes=len(orig),original_sha256=sha(orig),stored_bytes=len(b),stored_sha256=sha(b),storage='lossless gzip of HTTP-decoded response',authority='primary publisher; TLC candidate returns are redistricting derivative'))
 refs=[(STATE.parent/'ohio/data/baselines/raw/house-2024.pdf','clerk-2024-pdf','https://clerk.house.gov/member_info/electionInfo/2024/statistics2024.pdf'),(STATE.parent/'ohio/data/baselines/house-2024.txt','clerk-2024-text','https://clerk.house.gov/member_info/electionInfo/2024/statistics2024.pdf'),(STATE.parent/'michigan/data/baselines/house-statistics2020.pdf','clerk-2020-pdf','https://clerk.house.gov/member_info/electionInfo/2020/statistics2020.pdf'),(STATE.parent/'michigan/data/baselines/house-statistics2020.txt','clerk-2020-text','https://clerk.house.gov/member_info/electionInfo/2020/statistics2020.pdf')]
 for path,sid,url in refs:
  b=path.read_bytes();mp=STATE.parent/('ohio/data/baselines/raw/house-2024.pdf.meta.json' if '2024' in sid else 'michigan/data/baselines/primary-source-2020.json');md=json.loads(mp.read_text());original=path if path.suffix=='.pdf' else path.with_suffix('.pdf') if '2020' in sid else STATE.parent/'ohio/data/baselines/raw/house-2024.pdf';ob=original.read_bytes();sources.append(dict(source_id=sid,body_path=os.path.relpath(path,P),original_body_path=os.path.relpath(original,P),metadata_path=os.path.relpath(mp,P),requested_url=url,final_url=md.get('final_url',url),retrieved_at_utc=md['retrieved_utc'],http_status=md.get('status',md.get('http_status')),response_headers=md['headers'],original_sha256=sha(ob),stored_sha256=sha(b),original_bytes=len(ob),stored_bytes=len(b),storage='read-only PDF original' if path.suffix=='.pdf' else 'pdftotext layout derivative; original_body_path retains PDF',ownership='shared other-state evidence; no duplicate PDF',authority='House Clerk primary publication'))
 jwrite(P/'source-ledger.json',dict(observed_date='2026-10-18 UTC / 2026-10-17 Central',sources=sources,notes=['HTTP-decoded original payload hashes; compression preserves exact original bytes.','Archive capture datetime is not a certification or source-update date.','2024 statewide footer literal01/07/2025 10:42 AM; county footer literal07/01/2025 10.42 AM; date convention not inferred.','Raw OpenElections source filenames and literalcounty conflicts preserved; no silent allocation or dedup.','No source cadence or2026 precinct/ballot approval established.']))
 print('Source ledger',len(sources),'responses/references')
def assets():
 paths=[STATE/'county-partisanship.md',DATA/'county-baselines.csv']+[p for p in P.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in ['asset-manifest.json']]
 rows=[]
 for path in sorted(paths):
  assert path.stat().st_size<40000000,path
  rows.append(dict(path=os.path.relpath(path,STATE),bytes=path.stat().st_size,sha256=sha(path.read_bytes()),ownership='Texas partisanship worker exclusive writable scope'))
 jwrite(P/'asset-manifest.json',dict(asset_limit_strict_less_than_bytes=40000000,assets=rows,manifest_self_excluded='self hash would be circular; all other owned deliverables including validation.json are hashed',source_dependencies='source-ledger.json uses hash-addressed read-only originals'))
 print('Owned assets',len(rows),'largest',max(r['bytes'] for r in rows),'bytes')
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--assets',action='store_true');arg=a.parse_args();assets() if arg.assets else ledger()
