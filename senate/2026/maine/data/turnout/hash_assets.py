#!/usr/bin/env python3
"""Hash every owned deliverable/support asset except this manifest and audit output.
Run after edits/rebuilds, then validate_turnout.py. No timestamps or network calls.
"""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
STATE=ROOT.parent.parent
files=[p for p in ROOT.rglob('*') if p.is_file() and p.name not in ['asset-manifest.json','validation.json']]
files += [STATE/'turnout.md',STATE/'data/county-turnout.csv']
out=[]
for p in sorted(files):
    b=p.read_bytes();out.append(dict(path=str(p.relative_to(STATE)),bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
(ROOT/'asset-manifest.json').write_text(json.dumps(out,indent=2)+'\n')
print('Hashed',len(out),'owned files; raw byte hashes also independently retained in manifest.json')
