#!/usr/bin/env python3
"""Offline relative-link/asset-size audit and reproducible SHA-256 index.
Hash index is relative to this directory; scripts never modify shared inputs.
"""
import hashlib,json,pathlib,re,urllib.parse
P=pathlib.Path(__file__).resolve().parent
report=P.parent.parent/'county-partisanship.md'
links=[]
for match in re.finditer(r'\[[^\]]*\]\(([^)]+)\)',report.read_text()):
 target=match.group(1)
 if re.match(r'[a-z]+://',target):continue
 path=(report.parent/urllib.parse.unquote(target.split('#')[0])).resolve()
 assert path.exists() or path==P/'SHA256SUMS',('broken relative report link',target)
 links.append(target)
paths=[report,P.parent/'county-baselines.csv']+[p for p in sorted(P.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name not in ['SHA256SUMS','artifact-inventory.json']]
for p in paths:assert p.stat().st_size<40*1024*1024,('oversize',p)
records=[{'path':str(p.relative_to(P)) if p.is_relative_to(P) else '../../county-partisanship.md' if p==report else '../county-baselines.csv','bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]
inventory={'status':'PASS','relative_markdown_links_checked':len(links),'broken_relative_links':0,'files_indexed':len(records),'max_owned_asset_bytes':max(r['bytes'] for r in records),'all_owned_assets_under_40MiB':True,'files':records}
(P/'artifact-inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
records.append({'path':'artifact-inventory.json','sha256':hashlib.sha256((P/'artifact-inventory.json').read_bytes()).hexdigest()})
(P/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['path']+'\n' for r in records))
for target in links:assert (report.parent/urllib.parse.unquote(target.split('#')[0])).resolve().exists(),target
assert (P/'SHA256SUMS').stat().st_size<40*1024*1024
# Read back every stored asset through the exported relative manifest.
for line in (P/'SHA256SUMS').read_text().splitlines():
 digest,path=line.split('  ',1);assert hashlib.sha256((P/path).read_bytes()).hexdigest()==digest,path
print(json.dumps({k:v for k,v in inventory.items() if k!='files'},indent=2))
