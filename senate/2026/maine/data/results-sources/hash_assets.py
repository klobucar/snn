#!/usr/bin/env python3
from research import *
# Hash only this assignment, plus read-only pins. Do not hash or mutate peers' outputs wholesale.
inputs=['data/county-turnout.csv','data/turnout/priority-keys.txt','data/turnout/priority-set.json','data/turnout/source-vintage-diff.json','data/coordinator-baseline-reconciliation.json','data/coordinator-vintage-review.json','data/turnout/manifest.json','data/turnout/senate-2024-source-rows.csv','data/turnout/president-2024-source-rows.csv','data/turnout/governor-2022-source-rows.csv']
state=ROOT.parent.parent
pin={path:{'sha256':digest((state/path).read_bytes()),'bytes':(state/path).stat().st_size} for path in inputs}
(ROOT/'baseline-pin.json').write_text(json.dumps(pin,indent=2)+'\n')
assets=[]
for f in sorted(ROOT.rglob('*')):
 if not f.is_file() or f.name in ['asset-manifest.json','validation.json'] or '__pycache__' in f.parts:continue
 assets.append({'path':str(f.relative_to(ROOT)),'sha256':digest(f.read_bytes()),'bytes':f.stat().st_size})
for f in [ROOT.parent/'official-results-sources.csv',state/'official-results.md']:
 assets.append({'path':str(f.relative_to(ROOT)) if f.is_relative_to(ROOT) else ('../official-results-sources.csv' if f.name.endswith('.csv') else '../../official-results.md'),'sha256':digest(f.read_bytes()),'bytes':f.stat().st_size})
(ROOT/'asset-manifest.json').write_text(json.dumps({'algorithm':'SHA256','paths_relative_to':'data/results-sources','assets':assets},indent=2)+'\n')
print('assets',len(assets),'bytes',sum(x['bytes'] for x in assets),'largest',max(assets,key=lambda x:x['bytes']))
